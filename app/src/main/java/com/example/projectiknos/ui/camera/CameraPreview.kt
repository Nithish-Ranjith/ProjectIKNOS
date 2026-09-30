package com.example.projectiknos.ui.camera

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Camera
import androidx.compose.material.icons.filled.FlipCameraAndroid
import androidx.compose.material.icons.filled.NoPhotography
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import java.io.File
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.Executors

private const val TAG = "CameraPreview"

fun hasCameraPermission(context: Context): Boolean =
    ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED

@Composable
fun CameraPreview(
    modifier: Modifier = Modifier,
    showCaptureButton: Boolean = true,
    externalCaptureSignal: Int = 0,
    onPhotoCaptured: (File) -> Unit = {},
    overlayContent: @Composable (BoxScope.() -> Unit) = {}
) {
    val context = LocalContext.current
    var hasPerm by remember { mutableStateOf(hasCameraPermission(context)) }
    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> hasPerm = granted }

    if (!hasPerm) {
        LaunchedEffect(Unit) { permLauncher.launch(Manifest.permission.CAMERA) }
        CameraPermissionDeniedUI(onRequestAgain = { permLauncher.launch(Manifest.permission.CAMERA) })
        return
    }

    RealCameraPreview(
        modifier = modifier,
        showCaptureButton = showCaptureButton,
        externalCaptureSignal = externalCaptureSignal,
        onPhotoCaptured = onPhotoCaptured,
        overlayContent = overlayContent
    )
}

@Composable
private fun RealCameraPreview(
    modifier: Modifier,
    showCaptureButton: Boolean,
    externalCaptureSignal: Int,
    onPhotoCaptured: (File) -> Unit,
    overlayContent: @Composable BoxScope.() -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var lensFacing by remember { mutableIntStateOf(CameraSelector.LENS_FACING_BACK) }
    val imageCaptureRef = remember { mutableStateOf<ImageCapture?>(null) }
    val cameraExecutor = remember { Executors.newSingleThreadExecutor() }

    LaunchedEffect(externalCaptureSignal) {
        if (externalCaptureSignal > 0) {
            imageCaptureRef.value?.let { ic ->
                takePhoto(ic, context, cameraExecutor, onPhotoCaptured)
            }
        }
    }

    DisposableEffect(Unit) { onDispose { cameraExecutor.shutdown() } }

    Box(modifier = modifier) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                PreviewView(ctx).apply {
                    scaleType = PreviewView.ScaleType.FILL_CENTER
                    implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                }
            },
            update = { previewView ->
                val providerFuture = ProcessCameraProvider.getInstance(context)
                providerFuture.addListener({
                    val provider = providerFuture.get()
                    val preview = Preview.Builder().build().also {
                        it.setSurfaceProvider(previewView.surfaceProvider)
                    }
                    val ic = ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                        .setJpegQuality(92)
                        .setFlashMode(ImageCapture.FLASH_MODE_AUTO)
                        .build()
                    imageCaptureRef.value = ic
                    val selector = CameraSelector.Builder().requireLensFacing(lensFacing).build()
                    try {
                        provider.unbindAll()
                        provider.bindToLifecycle(lifecycleOwner, selector, preview, ic)
                    } catch (e: Exception) {
                        Log.e(TAG, "Camera bind failed: ${'$'}{e.message}")
                    }
                }, ContextCompat.getMainExecutor(context))
            }
        )

        overlayContent()

        Row(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .background(Color(0xAA000000))
                .padding(horizontal = 24.dp, vertical = 16.dp),
            horizontalArrangement = if (showCaptureButton) Arrangement.SpaceEvenly else Arrangement.End,
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (showCaptureButton) {
                IconButton(
                    onClick = {
                        imageCaptureRef.value?.let { ic ->
                            takePhoto(ic, context, cameraExecutor, onPhotoCaptured)
                        }
                    },
                    modifier = Modifier.size(72.dp).background(Color.White, CircleShape)
                ) {
                    Icon(Icons.Default.Camera, "Capture", tint = Color.Black, modifier = Modifier.size(36.dp))
                }
            }
            IconButton(
                onClick = {
                    lensFacing = if (lensFacing == CameraSelector.LENS_FACING_BACK)
                        CameraSelector.LENS_FACING_FRONT else CameraSelector.LENS_FACING_BACK
                },
                modifier = Modifier.size(48.dp)
            ) {
                Icon(Icons.Default.FlipCameraAndroid, "Flip camera", tint = Color.White, modifier = Modifier.size(28.dp))
            }
        }
    }
}

fun takePhoto(
    imageCapture: ImageCapture,
    context: Context,
    executor: java.util.concurrent.Executor,
    onPhotoCaptured: (File) -> Unit
) {
    val photoDir = File(context.cacheDir, "terratrace_photos").also { it.mkdirs() }
    val name = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(Date())
    val photoFile = File(photoDir, "IMG_${'$'}name.jpg")
    val outputOptions = ImageCapture.OutputFileOptions.Builder(photoFile).build()
    imageCapture.takePicture(outputOptions, executor, object : ImageCapture.OnImageSavedCallback {
        override fun onImageSaved(result: ImageCapture.OutputFileResults) {
            Log.d(TAG, "Photo saved: ${'$'}{photoFile.absolutePath}")
            onPhotoCaptured(photoFile)
        }
        override fun onError(exc: ImageCaptureException) {
            Log.e(TAG, "Photo capture failed: ${'$'}{exc.message}")
        }
    })
}

@Composable
fun CameraPermissionDeniedUI(onRequestAgain: () -> Unit) {
    Box(
        modifier = Modifier.fillMaxSize().background(Color(0xFF0F172A)),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp),
            modifier = Modifier.padding(32.dp)
        ) {
            Icon(Icons.Default.NoPhotography, null, tint = Color(0xFFEF4444), modifier = Modifier.size(64.dp))
            Text("Camera Permission Required", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
            Text(
                "TerraTrace needs camera access to capture field evidence and drone imagery.\n\nPlease grant the permission to continue.",
                color = Color(0xFF94A3B8), fontSize = 14.sp, textAlign = TextAlign.Center
            )
            Button(
                onClick = onRequestAgain,
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0284C7)),
                modifier = Modifier.fillMaxWidth()
            ) { Text("Grant Camera Permission", fontWeight = FontWeight.Bold) }
        }
    }
}
