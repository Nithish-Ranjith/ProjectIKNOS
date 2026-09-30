package com.example.projectiknos.auth

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import com.example.projectiknos.api.*
import kotlin.math.roundToInt

// Controls which step we're on
private enum class LoginStep { PHONE, OTP }

@Composable
fun LoginScreen(
    authManager: AuthManager,
    onLoginSuccess: (String) -> Unit
) {
    var step by remember { mutableStateOf(LoginStep.PHONE) }

    // Step 1: Phone
    var phone by remember { mutableStateOf("") }
    var serverUrl by remember { mutableStateOf(RetrofitClient.baseUrl) }
    var showServerConfig by remember { mutableStateOf(false) }

    // Step 2: OTP
    var otp by remember { mutableStateOf("") }
    var otpError by remember { mutableStateOf<String?>(null) }
    var otpShake by remember { mutableStateOf(false) }
    var countdown by remember { mutableIntStateOf(0) }

    var errorMessage by remember { mutableStateOf<String?>(null) }
    var isLoading by remember { mutableStateOf(false) }

    val coroutineScope = rememberCoroutineScope()
    val scrollState = rememberScrollState()

    // Shake animation offset
    val shakeOffset by animateIntOffsetAsState(
        targetValue = if (otpShake) IntOffset(10, 0) else IntOffset(0, 0),
        animationSpec = spring(dampingRatio = 0.3f, stiffness = Spring.StiffnessHigh),
        label = "shake"
    )

    // Countdown timer for OTP resend
    LaunchedEffect(countdown) {
        if (countdown > 0) {
            delay(1000)
            countdown--
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF0F172A))
            .verticalScroll(scrollState)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // --- Brand ---
        Surface(
            shape = RoundedCornerShape(8.dp),
            color = Color(0xFF1E293B),
            modifier = Modifier.padding(bottom = 8.dp)
        ) {
            Text(
                "CADASTRAL RECONCILIATION ENGINE",
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = Color(0xFF38BDF8),
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
            )
        }
        Text(
            "TerraTrace",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.ExtraBold,
            color = Color(0xFFF8FAFC),
            fontSize = 32.sp
        )
        Text(
            "Autonomous Survey & Ground Truth System",
            style = MaterialTheme.typography.bodySmall,
            color = Color(0xFF94A3B8),
            modifier = Modifier.padding(top = 4.dp, bottom = 28.dp)
        )

        // --- Server URL Config ---
        Card(
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B)),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp)
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text("Server Endpoint", fontSize = 12.sp, color = Color(0xFF94A3B8), fontWeight = FontWeight.SemiBold)
                        Text(RetrofitClient.baseUrl, fontSize = 12.sp, color = Color(0xFF38BDF8), fontFamily = FontFamily.Monospace)
                    }
                    TextButton(onClick = { showServerConfig = !showServerConfig }) {
                        Text(if (showServerConfig) "Hide" else "Change", color = Color(0xFF38BDF8), fontSize = 12.sp)
                    }
                }
                if (showServerConfig) {
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = serverUrl,
                        onValueChange = { serverUrl = it; RetrofitClient.baseUrl = it },
                        label = { Text("Server URL / IP", color = Color(0xFF94A3B8)) },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = Color.White, unfocusedTextColor = Color.White,
                            focusedBorderColor = Color(0xFF38BDF8), unfocusedBorderColor = Color(0xFF475569)
                        ),
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                }
            }
        }

        when (step) {
            // ======== STEP 1: PHONE ========
            LoginStep.PHONE -> {
                Text(
                    "Enter your phone number",
                    color = Color(0xFF94A3B8),
                    fontSize = 14.sp,
                    modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)
                )
                OutlinedTextField(
                    value = phone,
                    onValueChange = { phone = it },
                    label = { Text("Phone / Username", color = Color(0xFF94A3B8)) },
                    placeholder = { Text("+91 XXXXXXXXXX", color = Color(0xFF475569)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color.White, unfocusedTextColor = Color.White,
                        focusedBorderColor = Color(0xFF38BDF8), unfocusedBorderColor = Color(0xFF334155),
                        focusedLabelColor = Color(0xFF38BDF8), unfocusedLabelColor = Color(0xFF94A3B8)
                    ),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                if (errorMessage != null) {
                    Spacer(Modifier.height(12.dp))
                    Surface(
                        color = Color(0xFF7F1D1D),
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(errorMessage!!, color = Color(0xFFFECACA), fontSize = 13.sp, modifier = Modifier.padding(12.dp))
                    }
                }

                Spacer(Modifier.height(20.dp))
                Button(
                    onClick = {
                        if (phone.isBlank()) { errorMessage = "Please enter your phone number"; return@Button }
                        isLoading = true
                        errorMessage = null
                        RetrofitClient.baseUrl = serverUrl
                        coroutineScope.launch {
                            try {
                                RetrofitClient.instance.sendOtp(OtpSendRequest(phone.trim()))
                                countdown = 30
                                otp = ""
                                otpError = null
                                step = LoginStep.OTP
                            } catch (e: Exception) {
                                errorMessage = "Couldn't reach the server. Check your connection and try again.\n(${e.localizedMessage})"
                            } finally {
                                isLoading = false
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0284C7)),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth().height(50.dp),
                    enabled = !isLoading
                ) {
                    if (isLoading) CircularProgressIndicator(color = Color.White, modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
                    else Text("Send OTP", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                }

                // Dev fallback: direct username/password login
                Spacer(Modifier.height(24.dp))
                HorizontalDivider(color = Color(0xFF334155))
                Spacer(Modifier.height(12.dp))
                var devUser by remember { mutableStateOf("") }
                var devPass by remember { mutableStateOf("") }
                Text("Developer / Offline Login", color = Color(0xFF475569), fontSize = 11.sp, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = devUser, onValueChange = { devUser = it },
                    label = { Text("Username", color = Color(0xFF475569)) },
                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Color.White, unfocusedTextColor = Color.White, focusedBorderColor = Color(0xFF334155), unfocusedBorderColor = Color(0xFF1E293B)),
                    singleLine = true, modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = devPass, onValueChange = { devPass = it },
                    label = { Text("Password", color = Color(0xFF475569)) },
                    visualTransformation = PasswordVisualTransformation(),
                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Color.White, unfocusedTextColor = Color.White, focusedBorderColor = Color(0xFF334155), unfocusedBorderColor = Color(0xFF1E293B)),
                    singleLine = true, modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(8.dp))
                OutlinedButton(
                    onClick = {
                        if (devUser.isBlank() || devPass.isBlank()) return@OutlinedButton
                        isLoading = true; errorMessage = null
                        coroutineScope.launch {
                            try {
                                val r = RetrofitClient.instance.login(LoginRequest(devUser.trim(), devPass.trim()))
                                authManager.saveToken(r.access_token, r.role)
                                RetrofitClient.authToken = r.access_token
                                onLoginSuccess(r.role)
                            } catch (e: Exception) {
                                errorMessage = "Login failed: ${e.localizedMessage}"
                            } finally { isLoading = false }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFF475569)),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF334155)),
                    enabled = !isLoading
                ) { Text("Sign In (Dev)", fontSize = 13.sp) }
            }

            // ======== STEP 2: OTP ========
            LoginStep.OTP -> {
                Text(
                    "OTP sent to $phone",
                    color = Color(0xFF38BDF8),
                    fontSize = 14.sp,
                    modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp)
                )
                Text(
                    "Check the server log for your 6-digit code",
                    color = Color(0xFF64748B),
                    fontSize = 12.sp,
                    modifier = Modifier.fillMaxWidth().padding(bottom = 20.dp)
                )

                // OTP 6-digit input with shake
                OutlinedTextField(
                    value = otp,
                    onValueChange = { if (it.length <= 6) { otp = it; otpError = null; otpShake = false } },
                    label = { Text("6-digit OTP", color = Color(0xFF94A3B8)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color.White, unfocusedTextColor = Color.White,
                        focusedBorderColor = if (otpError != null) Color(0xFFEF4444) else Color(0xFF38BDF8),
                        unfocusedBorderColor = if (otpError != null) Color(0xFFEF4444) else Color(0xFF334155),
                    ),
                    isError = otpError != null,
                    supportingText = otpError?.let { { Text(it, color = Color(0xFFEF4444)) } },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().offset { shakeOffset }
                )

                Spacer(Modifier.height(12.dp))

                // Countdown timer / resend
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End
                ) {
                    if (countdown > 0) {
                        Text("Resend in 0:${countdown.toString().padStart(2, '0')}", color = Color(0xFF64748B), fontSize = 13.sp)
                    } else {
                        TextButton(onClick = {
                            coroutineScope.launch {
                                try {
                                    RetrofitClient.instance.sendOtp(OtpSendRequest(phone))
                                    countdown = 30
                                    otpError = null
                                } catch (e: Exception) { otpError = "Resend failed" }
                            }
                        }) { Text("Resend OTP", color = Color(0xFF38BDF8), fontSize = 13.sp) }
                    }
                }

                Spacer(Modifier.height(16.dp))
                Button(
                    onClick = {
                        if (otp.length != 6) { otpError = "Enter the 6-digit code"; return@Button }
                        isLoading = true; otpError = null
                        coroutineScope.launch {
                            try {
                                val r = RetrofitClient.instance.verifyOtp(OtpVerifyRequest(phone.trim(), otp.trim()))
                                authManager.saveToken(r.access_token, r.role)
                                RetrofitClient.authToken = r.access_token
                                onLoginSuccess(r.role)
                            } catch (e: Exception) {
                                val msg = e.message ?: ""
                                when {
                                    msg.contains("expired", ignoreCase = true) -> {
                                        otpError = "Code expired"
                                        countdown = 0
                                    }
                                    else -> {
                                        otpError = "Incorrect code"
                                        otpShake = true
                                        otp = ""
                                        coroutineScope.launch { delay(100); otpShake = false }
                                    }
                                }
                            } finally { isLoading = false }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0284C7)),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth().height(50.dp),
                    enabled = !isLoading && otp.length == 6
                ) {
                    if (isLoading) CircularProgressIndicator(color = Color.White, modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
                    else Text("Verify & Sign In", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                }

                Spacer(Modifier.height(16.dp))
                TextButton(onClick = { step = LoginStep.PHONE; errorMessage = null }) {
                    Text("← Change number", color = Color(0xFF64748B), fontSize = 13.sp)
                }
            }
        }
    }
}
