package com.example.projectiknos.surveyor_field

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import com.example.projectiknos.api.RetrofitClient

/**
 * Decision Screen — SURVEYOR_FIELD / SENIOR_FIELD.
 *
 * Decision flow:
 *   1. Surveyor selects: Reject | Escalate to Senior
 *   2. If escalate to update: Authority-gated Approve (SENIOR_FIELD required for
 *      OWNERSHIP/CADASTRAL_GEOMETRY; handled server-side).
 *
 * Design contracts:
 *   - "Approve Update" button requires a reason and update_class selection.
 *   - OWNERSHIP/CADASTRAL_GEOMETRY update_class requires SENIOR_FIELD tier — enforced
 *     server-side; if insufficient tier, the API returns 403 and we show the error.
 *   - "Reject" closes the case without a record update.
 *   - Escalate sets status to AUTHORITY_REVIEW for a senior officer to handle.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DecisionScreen(caseId: String, onBack: () -> Unit, onDecisionMade: () -> Unit) {
    var selectedDecision by remember { mutableStateOf<String?>(null) }
    var reason by remember { mutableStateOf("") }
    var updateClass by remember { mutableStateOf("OTHER_AUTHORIZED") }
    var updateClassExpanded by remember { mutableStateOf(false) }
    val updateClasses = listOf("OTHER_AUTHORIZED", "MUTATION", "OWNERSHIP", "CADASTRAL_GEOMETRY")
    var isSubmitting by remember { mutableStateOf(false) }
    var errorMsg by remember { mutableStateOf<String?>(null) }
    // PIN gate state
    var showPinGate by remember { mutableStateOf(false) }
    var pinEntry by remember { mutableStateOf("") }
    var pinError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Decision — Case #$caseId") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding).padding(16.dp)) {

            // Authority tier advisory
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                Row(Modifier.padding(12.dp), verticalAlignment = androidx.compose.ui.Alignment.Top) {
                    Icon(Icons.Default.Lock, null, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "OWNERSHIP and CADASTRAL_GEOMETRY updates require SENIOR_FIELD authority. " +
                        "If you are not SENIOR_FIELD, the server will reject the request.",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
            Spacer(Modifier.height(16.dp))

            Text("Select Decision", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(12.dp))

            // Decision options as outlined cards
            listOf(
                Triple("reject", "Reject Case", "Close without action — no discrepancy warranting record update."),
                Triple("escalate", "Escalate to Authority Review", "Send to SENIOR_FIELD for higher-tier decision."),
                Triple("approve_update", "Approve Record Update", "Write an authenticated, typed update to the land record.")
            ).forEach { (key, label, desc) ->
                OutlinedCard(
                    modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
                    colors = CardDefaults.outlinedCardColors(
                        containerColor = if (selectedDecision == key)
                            MaterialTheme.colorScheme.primaryContainer
                        else MaterialTheme.colorScheme.surface
                    ),
                    onClick = { selectedDecision = key }
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Text(label, fontWeight = FontWeight.SemiBold)
                        Text(desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }

            // Update class picker (only for approve_update)
            if (selectedDecision == "approve_update") {
                Spacer(Modifier.height(12.dp))
                Text("Update Class *", style = MaterialTheme.typography.labelLarge)
                ExposedDropdownMenuBox(expanded = updateClassExpanded, onExpandedChange = { updateClassExpanded = it }) {
                    OutlinedTextField(
                        value = updateClass,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Update Class") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(updateClassExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(expanded = updateClassExpanded, onDismissRequest = { updateClassExpanded = false }) {
                        updateClasses.forEach { uc ->
                            DropdownMenuItem(text = { Text(uc) }, onClick = { updateClass = uc; updateClassExpanded = false })
                        }
                    }
                }
                if (updateClass in listOf("OWNERSHIP", "CADASTRAL_GEOMETRY")) {
                    Spacer(Modifier.height(4.dp))
                    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Icon(Icons.Default.Warning, null, tint = Color(0xFFF57C00), modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Requires SENIOR_FIELD tier — server will enforce.", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF57C00))
                    }
                }
            }

            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = reason,
                onValueChange = { reason = it },
                label = { Text("Reason / Justification *") },
                modifier = Modifier.fillMaxWidth().height(100.dp),
                maxLines = 5
            )
            Spacer(Modifier.height(8.dp))

            if (errorMsg != null) {
                Text(errorMsg!!, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(8.dp))
            }

            val canSubmit = selectedDecision != null && reason.isNotBlank() && !isSubmitting
            Button(
                onClick = {
                    // Spec §2.3: Show PIN gate BEFORE any write
                    showPinGate = true
                    pinEntry = ""
                    pinError = null
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = canSubmit
            ) {
                Text("Confirm Decision")
            }
        }
    }

    // ---- PIN Re-authentication Dialog (must fire before write) ----
    if (showPinGate) {
        AlertDialog(
            onDismissRequest = { showPinGate = false },
            title = { Text("Authenticate Decision", fontWeight = FontWeight.Bold) },
            text = {
                Column {
                    Text(
                        "This decision will permanently update the land record. Re-enter your login password to confirm.",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(bottom = 12.dp)
                    )
                    OutlinedTextField(
                        value = pinEntry,
                        onValueChange = { pinEntry = it; pinError = null },
                        label = { Text("Login Password") },
                        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                        isError = pinError != null,
                        supportingText = pinError?.let { { Text(it, color = MaterialTheme.colorScheme.error) } },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (pinEntry.isBlank()) { pinError = "Password required"; return@Button }
                        showPinGate = false
                        isSubmitting = true
                        errorMsg = null
                        // Spec §2.3: Write fires AFTER auth confirmed
                        scope.launch {
                            try {
                                when (selectedDecision) {
                                    "reject" -> RetrofitClient.instance.submitDecision(caseId, mapOf("decision" to "reject", "reason" to reason))
                                    "escalate" -> RetrofitClient.instance.submitDecision(caseId, mapOf("decision" to "escalate", "reason" to reason))
                                    "approve_update" -> RetrofitClient.instance.submitApproval(caseId, mapOf("update_class" to updateClass, "reason" to reason))
                                }
                                onDecisionMade()
                            } catch (e: Exception) {
                                errorMsg = if (e.message?.contains("403") == true)
                                    "Insufficient authority tier for this update class."
                                else "Failed: ${e.localizedMessage}"
                                isSubmitting = false
                            }
                        }
                    }
                ) { Text("Confirm & Submit") }
            },
            dismissButton = {
                TextButton(onClick = { showPinGate = false }) { Text("Cancel") }
            }
        )
    }
}
