package com.example.projectiknos.api

// OTP request/response models
data class OtpSendRequest(val phone: String)
data class OtpSendResponse(val sent: Boolean, val expires_in: Int)
data class OtpVerifyRequest(val phone: String, val otp: String)
