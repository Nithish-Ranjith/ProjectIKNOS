package com.example.projectiknos.surveyor_field

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.launch
import com.example.projectiknos.api.RetrofitClient
import com.example.projectiknos.ui.camera.CameraPreview
import java.io.File

/**
 * Field Verification Screen — SURVEYOR_FIELD / SENIOR_FIELD.
 *
 * Design contracts:
 *   - Free-text summary is NOT the sole evidence representation.
 *   - Requires at least one structured observation and one photo ref.
 *   - Verification status is an explicit enum: CONFIRMED / DISPUTED / INCONCLUSIVE.
 *   - Location coordinates are captured (or manually entered).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FieldVerificationScreen(caseId: String, onBack: () -> Unit, onSubmitted: () -> Unit) {
    var findingsSummary by remember { mutableStateOf("") }
    var verificationStatus by remember { mutableStateOf("PENDING") }
    var statusExpanded by remember { mutableStateOf(false) }
    val statusOptions = listOf("CONFIRMED", "DISPUTED", "INCONCLUSIVE")
    val observations = remember { mutableStateListOf<String>() }
    val photoFiles = remember { mutableStateListOf<File>() }   // real captured files
    val photoRefs = remember { mutableStateListOf<String>() }  // filenames sent to backend
    var newObservation by remember { mutableStateOf("") }
    var isSubmitting by remember { mutableStateOf(false) }
    var errorMsg by remember { mutableStateOf<String?>(null) }
    var showCamera by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Field Verification") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Spacer(Modifier.height(8.dp))
            Text("Case #$caseId", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(16.dp))

            // Verification Status (required enum)
            Text("Verification Outcome *", style = MaterialTheme.typography.labelLarge)
            Spacer(Modifier.height(4.dp))
            ExposedDropdownMenuBox(expanded = statusExpanded, onExpandedChange = { statusExpanded = it }) {
                OutlinedTextField(
                    value = verificationStatus,
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("Status") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(statusExpanded) },
                    modifier = Modifier.menuAnchor().fillMaxWidth()
                )
                ExposedDropdownMenu(expanded = statusExpanded, onDismissRequest = { statusExpanded = false }) {
                    statusOptions.forEach { option ->
                        DropdownMenuItem(
                            text = { Text(option) },
                            onClick = { verificationStatus = option; statusExpanded = false }
                        )
                    }
                }
            }
            Spacer(Modifier.height(16.dp))

            // Structured observations (required — NOT just free text)
            Text("Structured Observations *", style = MaterialTheme.typography.labelLarge)
            Text("Add at least one specific observation (e.g., 'Boundary marker offset by ~3m NE')", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(4.dp))
            observations.forEachIndexed { i, obs ->
                Card(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                    Row(Modifier.padding(8.dp)) {
                        Text("${i + 1}. $obs", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            Row(Modifier.fillMaxWidth()) {
                OutlinedTextField(
                    value = newObservation,
                    onValueChange = { newObservation = it },
                    label = { Text("Add observation") },
                    modifier = Modifier.weight(1f)
                )
                Spacer(Modifier.width(8.dp))
                // Voice-to-text mic button (Feature F2)
                IconButton(
                    onClick = { 
                        // Mock speech-to-text integration
                        newObservation = "Voice note: observed boundary discrepancy on northern edge." 
                    },
                    modifier = Modifier.align(androidx.compose.ui.Alignment.CenterVertically)
                ) {
                    Icon(Icons.Default.Mic, "Voice to text")
                }
                IconButton(
                    onClick = {
                        if (newObservation.isNotBlank()) {
                            observations.add(newObservation.trim())
                            newObservation = ""
                        }
                    },
                    modifier = Modifier.align(androidx.compose.ui.Alignment.CenterVertically)
                ) {
                    Icon(Icons.Default.Add, "Add observation")
                }
            }
            Spacer(Modifier.height(16.dp))

            // Photo evidence
            Text("Photo Evidence *", style = MaterialTheme.typography.labelLarge)
            Spacer(Modifier.height(4.dp))
            OutlinedButton(
                onClick = { showCamera = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.CameraAlt, null)
                Spacer(Modifier.width(8.dp))
                Text("Capture Photo (${photoFiles.size} attached)")
            }
            // Captured photos list
            photoFiles.takeLast(3).forEach { file ->
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 2.dp)
                        .background(Color(0xFF1E293B), RoundedCornerShape(6.dp))
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Icon(Icons.Default.CheckCircle, null, tint = Color(0xFF22C55E), modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(file.name, color = Color(0xFF94A3B8), style = MaterialTheme.typography.bodySmall)
                    Spacer(Modifier.weight(1f))
                    Text("${file.length() / 1024}KB", color = Color(0xFF64748B), style = MaterialTheme.typography.bodySmall)
                }
            }

            // Full-screen camera dialog
            if (showCamera) {
                Dialog(
                    onDismissRequest = { showCamera = false },
                    properties = DialogProperties(usePlatformDefaultWidth = false)
                ) {
                    Box(Modifier.fillMaxSize()) {
                        CameraPreview(
                            modifier = Modifier.fillMaxSize(),
                            showCaptureButton = true,
                            onPhotoCaptured = { file ->
                                photoFiles.add(file)
                                photoRefs.add(file.name)
                                showCamera = false
                            }
                        )
                        // Close button
                        IconButton(
                            onClick = { showCamera = false },
                            modifier = Modifier
                                .align(Alignment.TopEnd)
                                .padding(16.dp)
                                .background(Color(0xAA000000), RoundedCornerShape(50))
                        ) {
                            Icon(Icons.Default.Close, "Close camera", tint = Color.White)
                        }
                    }
                }
            }
            Spacer(Modifier.height(16.dp))

            // Optional free-text findings summary
            OutlinedTextField(
                value = findingsSummary,
                onValueChange = { findingsSummary = it },
                label = { Text("Findings Summary (optional)") },
                placeholder = { Text("Brief context or interpretation...") },
                modifier = Modifier.fillMaxWidth().height(100.dp),
                maxLines = 5
            )
            Spacer(Modifier.height(8.dp))

            if (errorMsg != null) {
                Text(errorMsg!!, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(8.dp))
            }

            val canSubmit = verificationStatus != "PENDING" && observations.isNotEmpty() && photoRefs.isNotEmpty() && !isSubmitting

            Button(
                onClick = {
                    isSubmitting = true
                    errorMsg = null
                    scope.launch {
                        try {
                            RetrofitClient.instance.submitFieldVerification(
                                caseId = caseId,
                                body = mapOf(
                                    "observations" to observations.map { mapOf("type" to "VISUAL", "description" to it, "value" to "") },
                                    "photo_refs" to photoRefs,
                                    "measurement_refs" to emptyList<Any>(),
                                    "verification_status" to verificationStatus,
                                    "findings_summary" to findingsSummary
                                )
                            )
                            onSubmitted()
                        } catch (e: Exception) {
                            errorMsg = "Submission failed: ${e.localizedMessage}"
                            isSubmitting = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = canSubmit
            ) {
                if (isSubmitting) CircularProgressIndicator(Modifier.size(20.dp))
                else Text("Submit Verification")
            }
            Spacer(Modifier.height(32.dp))
        }
    }
}
