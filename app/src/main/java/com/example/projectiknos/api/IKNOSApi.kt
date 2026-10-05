package com.example.projectiknos.api

import retrofit2.http.*

data class LoginRequest(val username: String, val password: String)
data class TokenResponse(val access_token: String, val token_type: String, val role: String)
data class CaptureCommandResponse(val active: Boolean = false)

data class Case(
    val case_id: String,
    val parcel_id: String,
    val status: String,
    val confidence_score: Float,
    val action: String
)

interface IKNOSApi {

    // --- Auth ---
    @POST("auth/login")
    suspend fun login(@Body req: LoginRequest): TokenResponse

    @POST("auth/otp/send")
    suspend fun sendOtp(@Body req: OtpSendRequest): OtpSendResponse

    @POST("auth/otp/verify")
    suspend fun verifyOtp(@Body req: OtpVerifyRequest): TokenResponse

    // --- Cases ---
    @GET("cases")
    suspend fun getCases(@Query("status") status: String? = null): List<Case>

    @GET("my-cases")
    suspend fun getMyCases(): List<Case>

    @GET("cases/{case_id}")
    suspend fun getCase(@Path("case_id") caseId: String): Case

    @POST("cases/{case_id}/decision")
    suspend fun submitDecision(
        @Path("case_id") caseId: String,
        @Body body: Map<String, String>
    ): Map<String, String>

    @POST("cases/{case_id}/approve")
    suspend fun submitApproval(
        @Path("case_id") caseId: String,
        @Body body: Map<String, String>
    ): Map<String, String>

    @POST("cases/{case_id}/record-update")
    suspend fun submitRecordUpdate(
        @Path("case_id") caseId: String,
        @Body body: Map<String, Any>
    ): Map<String, String>

    @POST("cases/{case_id}/field-verification")
    suspend fun submitFieldVerification(
        @Path("case_id") caseId: String,
        @Body body: Map<String, Any>
    ): Map<String, String>

    @GET("cases/{case_id}/audit")
    suspend fun getAuditLog(@Path("case_id") caseId: String): List<Map<String, Any>>

    // --- Objections ---
    @POST("objections")
    suspend fun submitObjection(@Body body: Map<String, String>): Map<String, String>

    // --- Missions ---
    @POST("missions")
    suspend fun createMission(@Body body: Map<String, String>): Map<String, String>

    @PATCH("missions/{mission_id}/state")
    suspend fun updateMissionState(
        @Path("mission_id") missionId: String,
        @Body body: Map<String, String>
    ): Map<String, String>

    @Multipart
    @POST("missions/{mission_id}/images")
    suspend fun uploadMissionImage(
        @Path("mission_id") missionId: String,
        @Part("sidecar") sidecar: okhttp3.RequestBody,
        @Part file: okhttp3.MultipartBody.Part
    ): Map<String, Any>

    @GET("missions/{mission_id}/latest-image")
    suspend fun getLatestImage(
        @Path("mission_id") missionId: String
    ): Map<String, Any>

    @POST("command-capture")
    suspend fun triggerCaptureCommand(): Map<String, Any>

    @GET("command-capture")
    suspend fun pollCaptureCommand(): CaptureCommandResponse

    // --- Health check (offline detection) ---
    @GET("health")
    suspend fun getHealth(): Map<String, Any>

    // --- Offline sync flush ---
    @POST("sync/flush")
    suspend fun flushSyncQueue(
        @Body body: Map<String, Any>
    ): Map<String, Any>

    // --- Case images (for CaseDetailScreen photo strip) ---
    @GET("cases/{case_id}/images")
    suspend fun getCaseImages(
        @Path("case_id") caseId: String
    ): Map<String, Any>

    // --- Mission QC summary (for PostFlightQCScreen) ---
    @GET("missions/{mission_id}/qc-summary")
    suspend fun getMissionQcSummary(
        @Path("mission_id") missionId: String
    ): Map<String, Any>

    // --- Case-level spatial discrepancy (ML result from backend) ---
    @POST("cases/{case_id}/spatial-discrepancy")
    suspend fun computeSpatialDiscrepancy(
        @Path("case_id") caseId: String,
        @Body body: Map<String, Any>
    ): Map<String, Any>
}
