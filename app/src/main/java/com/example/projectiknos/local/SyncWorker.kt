package com.example.projectiknos.local

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
import androidx.work.*
import com.example.projectiknos.api.RetrofitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.concurrent.TimeUnit

private const val TAG = "SyncWorker"

/**
 * SyncWorker — Android WorkManager job that runs when the device reconnects to
 * the internet. It reads all PENDING entries from the Room sync_queue table,
 * POSTs them to /sync/flush in a single batch, and marks each one SENT or FAILED.
 *
 * Constraints: requires NETWORK (any — cellular or WiFi). Retries with exponential
 * backoff up to 5 times before marking entries FAILED.
 *
 * Scheduled by: SyncScheduler.schedulePeriodicSync() on app start and on
 * CONNECTIVITY_CHANGE broadcast (OfflineSyncBootReceiver).
 */
class SyncWorker(appContext: Context, params: WorkerParameters) :
    CoroutineWorker(appContext, params) {

    override suspend fun doWork(): androidx.work.ListenableWorker.Result = withContext(Dispatchers.IO) {
        val db      = AppDatabase.getDatabase(applicationContext)
        val syncDao = db.syncDao()

        val pending = syncDao.getPendingSyncEntries()
        if (pending.isEmpty()) {
            Log.d(TAG, "Sync queue empty — nothing to flush")
            return@withContext androidx.work.ListenableWorker.Result.success()
        }

        Log.i(TAG, "Flushing ${pending.size} pending sync entries to /sync/flush")

        // Build the batch payload
        val entriesJson = pending.map { entry ->
            mapOf(
                "local_id"   to entry.localId,
                "type"       to entry.type,
                "payload"    to JSONObject(entry.payload).toMap(),
                "created_at" to entry.createdAt
            )
        }

        return@withContext try {
            val response = RetrofitClient.instance.flushSyncQueue(
                mapOf("entries" to entriesJson)
            )

            // Mark each entry based on the server response
            val resultMap = (response["results"] as? List<*>)
                ?.filterIsInstance<Map<*, *>>()
                ?.associate { it["local_id"] as String to it["status"] as String }
                ?: emptyMap()

            pending.forEach { entry ->
                val serverStatus = resultMap[entry.localId] ?: "error"
                val newStatus = when (serverStatus) {
                    "applied", "queued" -> "sent"
                    else -> "failed"
                }
                syncDao.updateSyncStatus(entry.localId, newStatus)
                Log.d(TAG, "  ${entry.localId.take(8)} → $newStatus")
            }

            val applied = resultMap.values.count { it == "applied" || it == "queued" }
            val errors  = resultMap.values.count { it == "error" }
            Log.i(TAG, "Sync complete: $applied applied, $errors errors")

            if (errors > 0 && runAttemptCount < 4) androidx.work.ListenableWorker.Result.retry()
            else androidx.work.ListenableWorker.Result.success()

        } catch (e: Exception) {
            Log.e(TAG, "Sync flush failed: ${e.message}")
            pending.forEach { syncDao.updateSyncStatus(it.localId, "failed") }
            if (runAttemptCount < 4) androidx.work.ListenableWorker.Result.retry() else androidx.work.ListenableWorker.Result.failure()
        }
    }

    companion object {
        private const val WORK_NAME = "IKNOSSyncWorker"

        /** Call once on app startup — schedules periodic sync + immediate run. */
        fun schedulePeriodicSync(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            // Periodic: runs every 15 min when connected (WorkManager minimum)
            val periodic = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                periodic
            )
            Log.i(TAG, "Periodic sync scheduled (every 15 min, network required)")
        }

        /** Trigger an immediate one-shot sync (call on network reconnect). */
        fun triggerImmediateSync(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val oneShot = OneTimeWorkRequestBuilder<SyncWorker>()
                .setConstraints(constraints)
                .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
                .build()

            WorkManager.getInstance(context)
                .enqueueUniqueWork(
                    "${WORK_NAME}_immediate",
                    ExistingWorkPolicy.REPLACE,
                    oneShot
                )
            Log.i(TAG, "Immediate sync triggered")
        }

        /** Queue a new sync entry from any screen (thread-safe, suspending). */
        suspend fun enqueue(
            context: Context,
            type: String,
            payload: Map<String, Any>
        ) {
            val db    = AppDatabase.getDatabase(context)
            val entry = SyncQueueEntry(
                localId   = java.util.UUID.randomUUID().toString(),
                type      = type,
                payload   = org.json.JSONObject(payload).toString(),
                createdAt = System.currentTimeMillis(),
                status    = "pending",
                retryCount = 0
            )
            withContext(Dispatchers.IO) { db.syncDao().insertSyncEntry(entry) }
            Log.d(TAG, "Queued offline entry: type=$type id=${entry.localId.take(8)}")
        }
    }
}

/** Extension to convert JSONObject → Map (needed for payload serialization). */
private fun JSONObject.toMap(): Map<String, Any> {
    val map = mutableMapOf<String, Any>()
    keys().forEach { key -> map[key] = get(key) }
    return map
}
