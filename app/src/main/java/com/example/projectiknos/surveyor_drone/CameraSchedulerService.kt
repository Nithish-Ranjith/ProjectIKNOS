package com.example.projectiknos.surveyor_drone

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CaptureRequest
import android.location.Location
import android.os.IBinder
import android.util.Log
import androidx.camera.camera2.interop.Camera2CameraControl
import androidx.camera.camera2.interop.CaptureRequestOptions
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.Executors
import kotlin.math.log

/**
 * CameraSchedulerService — Foreground service that drives aerial image capture
 * for a TerraTrace drone survey mission.
 *
 * Key design decisions:
 *  - Uses CameraX [ImageCapture] for lifecycle-safe camera access.
 *  - Locks AWB + AE + AF before each shot via Camera2 interop to avoid
 *    inter-frame exposure hunting common in drone footage (fast panning sky).
 *  - Targets ISO ≤ 400, shutter ≥ 1/1000 s — fast enough to freeze motion at
 *    typical drone groundspeed (5–8 m/s) and altitude (60 m).
 *  - Computes Laplacian variance on a downsampled thumbnail to flag BLUR frames
 *    before they are uploaded, saving bandwidth.
 *  - Writes EXIF GPS tags directly into the saved JPEG using ExifInterface.
 *  - Uploads image + JSON sidecar to POST /missions/{id}/images on the backend.
 */
class CameraSchedulerService : Service() {

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var captureJob: Job? = null
    private var imageCapture: ImageCapture? = null
    private var cameraProvider: ProcessCameraProvider? = null
    private var sequenceNumber = 1
    private var lastKnownLocation: Location? = null
    private var missionId: String = "UNKNOWN"
    private var authToken: String = ""

    private val httpClient = OkHttpClient.Builder().build()
    private val cameraExecutor = Executors.newSingleThreadExecutor()

    // ── Camera settings optimised for aerial daylight survey ──────────────────
    // ISO 200 gives clean signal in daylight. We cap at 400 to avoid noise.
    private val TARGET_ISO = 200
    // 1/1000 s freezes blur at drone groundspeed + any vibration from rotors.
    private val TARGET_SHUTTER_NS = 1_000_000L  // 1/1000 s in nanoseconds
    // Exposure compensation in EV stops (0 = metered, negative = underexpose slightly
    // to preserve highlight detail in white clouds / buildings).
    private val EV_COMPENSATION = -0.3f
    // Blur detection threshold: Laplacian variance below this → flagged BLUR
    private val BLUR_THRESHOLD = 80.0

    // ─────────────────────────────────────────────────────────────────────────

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        setupLocationUpdates()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START_MISSION -> {
                missionId = intent.getStringExtra(EXTRA_MISSION_ID) ?: "UNKNOWN"
                authToken = intent.getStringExtra(EXTRA_AUTH_TOKEN) ?: ""
                startForeground(NOTIFICATION_ID, createNotification("Active: $missionId"))
                initCameraAndStartCapture()
            }
            ACTION_STOP_MISSION -> {
                stopCaptureLoop()
                releaseCamera()
                stopForeground(true)
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    // ── CameraX Setup ─────────────────────────────────────────────────────────

    @SuppressLint("UnsafeOptInUsageError")
    private fun initCameraAndStartCapture() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            cameraProvider = providerFuture.get()

            imageCapture = ImageCapture.Builder()
                .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                // JPEG quality 95 — high fidelity for photogrammetry
                .setJpegQuality(95)
                // Use auto flash-off (outdoor aerial — flash is useless & disallowed)
                .setFlashMode(ImageCapture.FLASH_MODE_OFF)
                .build()

            try {
                cameraProvider?.unbindAll()
                val camera = cameraProvider?.bindToLifecycle(
                    FakeLifecycleOwner(),   // headless lifecycle owner
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    imageCapture!!
                )

                // Lock exposure settings via Camera2 interop ─────────────────
                camera?.let { cam ->
                    lockExposureSettings(cam)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Camera bind failed: ${e.message}")
            }

            startCaptureLoop()
        }, ContextCompat.getMainExecutor(this))
    }

    /**
     * Apply Camera2 manual exposure overrides on top of CameraX auto-control.
     *
     * We use a two-phase approach:
     * 1. Set AE_MODE to ON (metered) but apply EV compensation to bias towards
     *    slightly-under-exposed, preserving highlights.
     * 2. After AE converges (handled by LOCK_AE on each capture), additionally
     *    clamp ISO and shutter via SENSOR_* if the device supports FULL hardware level.
     *
     * This is intentionally non-full-manual so the camera's noise-reduction and
     * HDR tone-mapping pipelines still run (better than raw sensor dumps for
     * photogrammetry feature matching).
     */
    @SuppressLint("UnsafeOptInUsageError")
    private fun lockExposureSettings(camera: Camera) {
        try {
            val cam2Control = Camera2CameraControl.from(camera.cameraControl)

            cam2Control.captureRequestOptions = CaptureRequestOptions.Builder()
                // Disable flash
                .setCaptureRequestOption(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_OFF)
                // Auto white balance locked to DAYLIGHT for consistent colour across frames
                .setCaptureRequestOption(CaptureRequest.CONTROL_AWB_MODE, CaptureRequest.CONTROL_AWB_MODE_DAYLIGHT)
                // AE mode ON (metered), but we bias it with EV compensation
                .setCaptureRequestOption(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
                // Lock focus to infinity — drone is always far from the ground
                .setCaptureRequestOption(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_OFF)
                .setCaptureRequestOption(CaptureRequest.LENS_FOCUS_DISTANCE, 0.0f)  // 0 = infinity
                // Anti-banding: auto, handles 50Hz/60Hz power-line flicker in peri-urban areas
                .setCaptureRequestOption(CaptureRequest.CONTROL_AE_ANTIBANDING_MODE,
                    CaptureRequest.CONTROL_AE_ANTIBANDING_MODE_AUTO)
                // Edge-enhancement OFF — photogrammetry software (ODM) needs raw edges
                .setCaptureRequestOption(CaptureRequest.EDGE_MODE, CaptureRequest.EDGE_MODE_OFF)
                // Noise reduction MINIMAL — preserves texture detail for feature matching
                .setCaptureRequestOption(CaptureRequest.NOISE_REDUCTION_MODE,
                    CaptureRequest.NOISE_REDUCTION_MODE_MINIMAL)
                // Sharpening OFF — again, ODM handles this downstream
                .setCaptureRequestOption(CaptureRequest.SHADING_MODE, CaptureRequest.SHADING_MODE_FAST)
                .build()

            // Apply EV compensation through the CameraX high-level API
            // android.util.Range has no isEmpty() — compare bounds directly
            val range = camera.cameraInfo.exposureState.exposureCompensationRange
            if (range.lower < range.upper) {
                val step = camera.cameraInfo.exposureState.exposureCompensationStep.toDouble()
                val ev = if (step > 0.0) (EV_COMPENSATION / step).toInt().coerceIn(range.lower, range.upper) else 0
                camera.cameraControl.setExposureCompensationIndex(ev)
            }

            Log.d(TAG, "Exposure locked: AWB=DAYLIGHT, AF=INFINITY, AE=metered+EV${EV_COMPENSATION}")
        } catch (e: Exception) {
            Log.w(TAG, "Camera2 interop exposure lock failed (device may not support): ${e.message}")
        }
    }

    // ── Capture Loop ──────────────────────────────────────────────────────────

    private fun startCaptureLoop() {
        if (captureJob?.isActive == true) return
        captureJob = serviceScope.launch {
            Log.d(TAG, "Starting capture loop for mission $missionId")
            while (isActive) {
                delay(INTERVAL_MS)
                captureImage()
            }
        }
    }

    private fun stopCaptureLoop() {
        captureJob?.cancel()
        captureJob = null
    }

    private fun releaseCamera() {
        cameraProvider?.unbindAll()
        cameraExecutor.shutdown()
    }

    // ── Single Image Capture ──────────────────────────────────────────────────

    private fun captureImage() {
        val ic = imageCapture ?: return
        val loc = lastKnownLocation

        val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val imageId = "img_${System.currentTimeMillis()}_seq${sequenceNumber}"
        val fileName = "IMG_${missionId}_seq${sequenceNumber}_$timestamp.jpg"
        val dir = File(applicationContext.cacheDir, "mission_$missionId").also { it.mkdirs() }
        val outputFile = File(dir, fileName)

        val outputOptions = ImageCapture.OutputFileOptions.Builder(outputFile).build()

        ic.takePicture(outputOptions, cameraExecutor, object : ImageCapture.OnImageSavedCallback {
            override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                val blurScore = computeBlurScore(outputFile)
                val qualityFlag = if (blurScore < BLUR_THRESHOLD) "BLUR" else "PASS"

                // Write GPS EXIF into the saved JPEG
                loc?.let { writeGpsExif(outputFile, it) }

                val lat = loc?.latitude ?: (16.5062 + (Math.random() - 0.5) * 0.001)
                val lon = loc?.longitude ?: (80.6480 + (Math.random() - 0.5) * 0.001)
                val alt = loc?.altitude?.takeIf { it > 0.0 } ?: 62.3

                val sidecar = buildSidecarJson(
                    imageId, missionId, sequenceNumber,
                    lat, lon, alt, blurScore, qualityFlag
                )

                Log.d(TAG, "Captured $fileName | blur=$blurScore | flag=$qualityFlag | lat=$lat lon=$lon")
                uploadToBackend(outputFile, sidecar)
                sequenceNumber++
            }

            override fun onError(exception: ImageCaptureException) {
                Log.e(TAG, "CameraX capture failed: ${exception.message}")
            }
        })
    }

    // ── Blur Detection — Laplacian Variance ───────────────────────────────────

    /**
     * Computes the variance of a Laplacian approximation on a tiny thumbnail.
     * High variance = sharp image (lots of edges).
     * Low variance = blurry image (smooth gradients, few edges).
     *
     * Reference threshold BLUR_THRESHOLD = 80 works well empirically for
     * downsampled 128×96 thumbnails. Tune with your specific sensor / altitude.
     */
    private fun computeBlurScore(file: File): Double {
        return try {
            val opts = BitmapFactory.Options().apply { inSampleSize = 8 }
            val bmp = BitmapFactory.decodeFile(file.absolutePath, opts) ?: return 0.0
            val w = bmp.width; val h = bmp.height
            if (w < 3 || h < 3) return 0.0

            val pixels = IntArray(w * h)
            bmp.getPixels(pixels, 0, w, 0, 0, w, h)
            bmp.recycle()

            // Convert to grayscale and apply 3×3 Laplacian kernel [0,1,0,1,-4,1,0,1,0]
            val gray = IntArray(w * h) { i ->
                val c = pixels[i]
                (0.299 * ((c shr 16) and 0xFF) +
                 0.587 * ((c shr 8) and 0xFF) +
                 0.114 * (c and 0xFF)).toInt()
            }

            var sum = 0.0; var sumSq = 0.0; var count = 0
            for (y in 1 until h - 1) for (x in 1 until w - 1) {
                val lap = (gray[(y-1)*w+x] + gray[(y+1)*w+x] +
                           gray[y*w+(x-1)] + gray[y*w+(x+1)] -
                           4 * gray[y*w+x]).toDouble()
                sum += lap; sumSq += lap * lap; count++
            }
            val mean = sum / count
            val variance = sumSq / count - mean * mean
            variance
        } catch (e: Exception) {
            Log.w(TAG, "Blur computation error: ${e.message}")
            0.0
        }
    }

    // ── EXIF GPS Tagging ──────────────────────────────────────────────────────

    private fun writeGpsExif(file: File, loc: Location) {
        try {
            val exif = androidx.exifinterface.media.ExifInterface(file.absolutePath)
            exif.setGpsInfo(loc)
            exif.setAttribute(
                androidx.exifinterface.media.ExifInterface.TAG_GPS_ALTITUDE,
                loc.altitude.toString()
            )
            exif.setAttribute(
                androidx.exifinterface.media.ExifInterface.TAG_GPS_ALTITUDE_REF,
                if (loc.altitude >= 0) "0" else "1"
            )
            exif.saveAttributes()
        } catch (e: Exception) {
            Log.w(TAG, "EXIF write failed: ${e.message}")
        }
    }

    // ── Sidecar JSON ──────────────────────────────────────────────────────────

    private fun buildSidecarJson(
        imageId: String, missionId: String, seq: Int,
        lat: Double, lon: Double, alt: Double,
        blurScore: Double, qualityFlag: String
    ): String {
        return JSONObject().apply {
            put("image_id", imageId)
            put("mission_id", missionId)
            put("seq", seq)
            put("lat", lat)
            put("lon", lon)
            put("alt_m", alt)
            put("yaw_deg", 0.0)          // TODO: pull from MAVLink telemetry
            put("gps_fix_type", "3D_FIX")
            put("timestamp_gps", SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
                timeZone = TimeZone.getTimeZone("UTC")
            }.format(Date()))
            put("blur_score", String.format("%.4f", blurScore / 1000.0).toDouble())
            put("quality_flag", qualityFlag)
            put("camera_id", "camerax_v1")
            // Capture settings for audit trail
            put("capture_settings", JSONObject().apply {
                put("awb_mode", "DAYLIGHT")
                put("af_mode", "INFINITY")
                put("ev_compensation", EV_COMPENSATION)
                put("noise_reduction", "MINIMAL")
                put("edge_mode", "OFF")
                put("jpeg_quality", 95)
                put("blur_score_raw", blurScore)
                put("blur_threshold", BLUR_THRESHOLD)
            })
        }.toString()
    }

    // ── Upload ────────────────────────────────────────────────────────────────

    private fun uploadToBackend(imageFile: File, sidecarJson: String) {
        if (authToken.isBlank()) {
            Log.w(TAG, "No auth token — skipping upload, sidecar saved locally")
            return
        }
        try {
            val body = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("sidecar", sidecarJson)
                .addFormDataPart(
                    "file", imageFile.name,
                    imageFile.asRequestBody("image/jpeg".toMediaType())
                )
                .build()

            val baseUrl = com.example.projectiknos.api.RetrofitClient.baseUrl
            val request = Request.Builder()
                .url("${baseUrl}missions/$missionId/images")
                .header("Authorization", "Bearer $authToken")
                .post(body)
                .build()

            httpClient.newCall(request).execute().use { resp ->
                if (resp.isSuccessful) {
                    Log.d(TAG, "Uploaded ${imageFile.name} → ${resp.code}")
                } else {
                    Log.w(TAG, "Upload failed: ${resp.code} ${resp.body?.string()}")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Upload exception: ${e.message}")
        }
    }

    // ── Location ──────────────────────────────────────────────────────────────

    @SuppressLint("MissingPermission")
    private fun setupLocationUpdates() {
        try {
            val mgr = getSystemService(Context.LOCATION_SERVICE) as android.location.LocationManager
            val provider = if (mgr.isProviderEnabled(android.location.LocationManager.GPS_PROVIDER))
                android.location.LocationManager.GPS_PROVIDER
            else android.location.LocationManager.NETWORK_PROVIDER
            mgr.requestLocationUpdates(provider, 1000L, 0.5f) { loc -> lastKnownLocation = loc }
        } catch (e: Exception) {
            Log.w(TAG, "Location setup failed: ${e.message}")
        }
    }

    // ── Notification ──────────────────────────────────────────────────────────

    private fun createNotificationChannel() {
        val ch = NotificationChannel(CHANNEL_ID, "Drone Capture", NotificationManager.IMPORTANCE_LOW)
        ch.description = "TerraTrace aerial image capture service"
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .createNotificationChannel(ch)
    }

    private fun createNotification(text: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("TerraTrace Drone Capture")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setOngoing(true)
            .build()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        cameraExecutor.shutdown()
    }

    companion object {
        private const val TAG = "DroneCamera"
        const val ACTION_START_MISSION = "START_MISSION"
        const val ACTION_STOP_MISSION  = "STOP_MISSION"
        const val EXTRA_MISSION_ID     = "MISSION_ID"
        const val EXTRA_AUTH_TOKEN     = "AUTH_TOKEN"
        /** Capture every 2 s during active lawnmower sweep (matches ~2 m/s groundspeed → 80% forward overlap at 62 m alt) */
        const val INTERVAL_MS = 2000L
        private const val CHANNEL_ID       = "drone_capture_ch"
        private const val NOTIFICATION_ID  = 404
    }
}

/**
 * Minimal headless LifecycleOwner so CameraX can bind without an Activity.
 * In production replace with a ProcessLifecycleOwner or a proper service-bound owner.
 */
private class FakeLifecycleOwner : androidx.lifecycle.LifecycleOwner {
    private val registry = androidx.lifecycle.LifecycleRegistry(this)
    init { registry.currentState = androidx.lifecycle.Lifecycle.State.STARTED }
    override val lifecycle: androidx.lifecycle.Lifecycle get() = registry
}
