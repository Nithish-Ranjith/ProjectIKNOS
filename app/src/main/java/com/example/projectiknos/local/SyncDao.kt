package com.example.projectiknos.local

import androidx.room.*

@Entity(tableName = "sync_queue")
data class SyncQueueEntry(
    @PrimaryKey val localId: String,      // UUID generated offline
    val type: String,                      // "decision" | "field_note" | "objection"
    val payload: String,                   // JSON payload
    val createdAt: Long,
    val status: String,                    // "pending" | "sent" | "failed"
    val retryCount: Int = 0
)

@Entity(tableName = "cached_cases")
data class CachedCase(
    @PrimaryKey val caseId: String,
    val parcelId: String,
    val confidenceScore: Float,
    val status: String,
    val caseDataJson: String,
    val cachedAt: Long
)

@Dao
interface SyncDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertSyncEntry(entry: SyncQueueEntry)

    @Query("SELECT * FROM sync_queue WHERE status = 'pending' ORDER BY createdAt ASC")
    suspend fun getPendingSyncEntries(): List<SyncQueueEntry>

    @Query("UPDATE sync_queue SET status = :newStatus, retryCount = retryCount + 1 WHERE localId = :localId")
    suspend fun updateSyncStatus(localId: String, newStatus: String)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCachedCases(cases: List<CachedCase>)

    @Query("SELECT * FROM cached_cases")
    suspend fun getAllCachedCases(): List<CachedCase>

    @Query("DELETE FROM cached_cases")
    suspend fun clearCachedCases()
}
