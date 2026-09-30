package com.example.projectiknos.customer

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import com.example.projectiknos.api.RetrofitClient
import retrofit2.http.Body
import retrofit2.http.POST

data class ObjectionRequest(
    val parcel_id: String,
    val text: String,
    val evidence_photo_ref: String? = null
)

/**
 * File Objection — CUSTOMER role only.
 *
 * Design contracts:
 *   - Submitting an objection does NOT lock the parcel or open a case.
 *   - It creates a grievance record that a SURVEYOR_FIELD must review.
 *   - The system explicitly tells the customer this on submission.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FileObjectionScreen(parcelId: String, onBack: () -> Unit) {
    var text by remember { mutableStateOf("") }
    var isSubmitting by remember { mutableStateOf(false) }
    var submitResult by remember { mutableStateOf<String?>(null) }
    var isError by remember { mutableStateOf(false) }
    val photoRefs = remember { mutableStateListOf<String>() }
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("File Objection") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .padding(16.dp)
                .fillMaxSize()
        ) {
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("Parcel: $parcelId", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Your objection will be reviewed by an authorized surveyor before any action is taken. " +
                        "Submitting this form does not guarantee an investigation will be opened.",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
            Spacer(Modifier.height(16.dp))

            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                label = { Text("Describe your objection") },
                placeholder = { Text("e.g., The boundary shown does not match the actual fence line...") },
                modifier = Modifier.fillMaxWidth().height(150.dp),
                maxLines = 8
            )
            Spacer(Modifier.height(8.dp))

            // Multi-photo upload picker (Feature C4)
            OutlinedButton(
                onClick = {
                    if (photoRefs.size < 5) {
                        photoRefs.add("objection_photo_${photoRefs.size + 1}_${System.currentTimeMillis()}.jpg")
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = photoRefs.size < 5
            ) {
                Icon(Icons.Default.CameraAlt, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Attach Photo Evidence (${photoRefs.size}/5)")
            }
            if (photoRefs.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    photoRefs.forEachIndexed { index, _ ->
                        Card(
                            modifier = Modifier.size(60.dp),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                        ) {
                            Box(Modifier.fillMaxSize(), contentAlignment = androidx.compose.ui.Alignment.Center) {
                                Text("IMG\n${index+1}", style = MaterialTheme.typography.labelSmall)
                            }
                        }
                    }
                }
            }
            Spacer(Modifier.height(24.dp))

            if (submitResult != null) {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = if (isError) MaterialTheme.colorScheme.errorContainer
                                         else MaterialTheme.colorScheme.primaryContainer
                    )
                ) {
                    Text(submitResult!!, Modifier.padding(12.dp))
                }
                Spacer(Modifier.height(16.dp))
            }

            Button(
                onClick = {
                    if (text.isBlank()) return@Button
                    isSubmitting = true
                    scope.launch {
                        try {
                            // POST /objections
                            RetrofitClient.instance.submitObjection(
                                mapOf("parcel_id" to parcelId, "text" to text)
                            )
                            submitResult = "Objection submitted. A surveyor will review your case. " +
                                "You will not receive automatic updates — contact your local land records office."
                            isError = false
                        } catch (e: Exception) {
                            submitResult = "Submission failed: ${e.localizedMessage}"
                            isError = true
                        } finally {
                            isSubmitting = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = text.isNotBlank() && !isSubmitting
            ) {
                if (isSubmitting) CircularProgressIndicator(Modifier.size(20.dp))
                else Text("Submit Objection")
            }
        }
    }
}
