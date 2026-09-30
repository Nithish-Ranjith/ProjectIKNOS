package com.example.projectiknos.surveyor_field

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import com.example.projectiknos.api.RetrofitClient
import com.example.projectiknos.api.Case

/**
 * PreFlight Screen — SURVEYOR_DRONE role.
 *
 * Checks:
 *   1. Active case with parcel to survey
 *   2. Drone armed/heartbeat (via telemetry relay — mocked for now)
 *   3. Camera profile + grid parameters reviewed
 *   4. Flight mode advisory: LOITER required (not autonomous)
 *
 * Design contracts:
 *   - This is a HUMAN-OPERATED survey. LOITER mode only.
 *   - The tablet does NOT command the drone. The pilot commands the drone manually.
 *   - The app shows a checklist; the pilot must check each item.
 *   - Mission is only created (DRAFT) after all checklist items pass.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PreFlightScreen(
    onNavigateToAOI: (String) -> Unit,
    onLogout: () -> Unit
) {
    var cases by remember { mutableStateOf<List<Case>>(emptyList()) }
    var selectedCase by remember { mutableStateOf<Case?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    val checklistItems = remember {
        mutableStateListOf(
            "Drone powered on and GPS acquired" to false,
            "Flight controller in LOITER mode" to false,
            "Camera physically mounted and connected to Pi" to false,
            "PiCamera2 service running (check Pi SSH)" to false,
            "MAVLink connection confirmed (Pi telemetry active)" to false,
            "Battery > 50%" to false,
            "AOI perimeter walk completed or GeoJSON loaded" to false,
            "Local weather checked — wind < 15 km/h" to false,
        )
    }
    val allChecked by remember { derivedStateOf { checklistItems.all { it.second } } }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        scope.launch {
            try {
                cases = RetrofitClient.instance.getCases("open")
            } catch (e: Exception) { /* handled below */ }
            finally { isLoading = false }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pre-Flight Checklist") },
                actions = { TextButton(onClick = onLogout) { Text("Logout") } }
            )
        }
    ) { padding ->
        Column(
            Modifier.padding(padding).padding(16.dp).verticalScroll(rememberScrollState())
        ) {
            // LOITER advisory banner
            Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3E0))) {
                Row(Modifier.padding(12.dp), verticalAlignment = Alignment.Top) {
                    Icon(Icons.Default.Info, null, tint = Color(0xFFF57C00), modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                    Column {
                        Text("Human-Operated Survey Only", fontWeight = FontWeight.Bold, color = Color(0xFFE65100))
                        Text(
                            "This is NOT an autonomous flight. The drone is flown manually in LOITER mode. " +
                            "The tablet provides planning tools and image capture — it does NOT send flight commands.",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
            Spacer(Modifier.height(16.dp))

            // Case picker
            Text("Select Case to Survey", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            if (isLoading) {
                CircularProgressIndicator()
            } else {
                cases.forEach { case ->
                    OutlinedCard(
                        modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp),
                        colors = CardDefaults.outlinedCardColors(
                            containerColor = if (selectedCase?.case_id == case.case_id)
                                MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface
                        ),
                        onClick = { selectedCase = case }
                    ) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text("Case #${case.case_id}", fontWeight = FontWeight.Medium)
                                Text("Parcel: ${case.parcel_id}", style = MaterialTheme.typography.bodySmall)
                            }
                            if (selectedCase?.case_id == case.case_id)
                                Icon(Icons.Default.Check, null, tint = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
            Spacer(Modifier.height(20.dp))

            // Checklist
            Text("Pre-Flight Checklist", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            checklistItems.forEachIndexed { i, (label, checked) ->
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Checkbox(
                        checked = checked,
                        onCheckedChange = { checklistItems[i] = label to it }
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(label, style = MaterialTheme.typography.bodyMedium)
                }
            }
            Spacer(Modifier.height(24.dp))

            Button(
                onClick = { selectedCase?.let { onNavigateToAOI(it.case_id) } },
                modifier = Modifier.fillMaxWidth(),
                enabled = allChecked && selectedCase != null
            ) {
                Icon(Icons.Default.Map, null)
                Spacer(Modifier.width(8.dp))
                Text("Proceed to AOI Planning")
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}
