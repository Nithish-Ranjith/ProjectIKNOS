package com.example.projectiknos.local

import androidx.room.*

@Entity(tableName = "cases_local")
data class CaseEntity(
    @PrimaryKey val case_id: String,
    val parcel_id: String,
    val status: String,
    val confidence_score: Float,
    val action: String,
    val needs_sync: Boolean = false
)

@Dao
interface CaseDao {
    @Query("SELECT * FROM cases_local")
    suspend fun getAllCases(): List<CaseEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCases(cases: List<CaseEntity>)
    
    @Query("SELECT * FROM cases_local WHERE needs_sync = 1")
    suspend fun getUnsyncedCases(): List<CaseEntity>
}
