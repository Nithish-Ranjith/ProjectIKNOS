package com.example.projectiknos.surveyor_field

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.outlined.Circle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.projectiknos.ui.theme.*

data class ChecklistItem(val id: String, val text: String, var isChecked: Boolean = false)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PreFlightChecklistScreen(missionId: String, onBack: () -> Unit, onStartMission: () -> Unit) {
    val checklist = remember {
        mutableStateListOf(
            ChecklistItem("gps", "GPS fix acquired (≥6 satellites)"),
            ChecklistItem("battery", "Drone and controller battery ≥80%"),
            ChecklistItem("propellers", "Propellers inspected and secure"),
            ChecklistItem("airspace", "DGCA DigitalSky no-fly zone verified clear"),
            ChecklistItem("weather", "Weather conditions clear (no rain, wind <10m/s)"),
            ChecklistItem("camera", "Camera test shot confirmed and SD card mounted")
        )
    }
    val allChecked = checklist.all { it.isChecked }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pre-Flight Safety Check") },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, contentDescription = "Back") }
                }
            )
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize().padding(16.dp)) {
            Card(colors = CardDefaults.cardColors(containerColor = PanelColor)) {
                Column(Modifier.padding(16.dp)) {
                    Text("Mission: $missionId", style = MaterialTheme.typography.titleMedium, color = TextPrimary)
                    Spacer(Modifier.height(4.dp))
                    Text("All safety items must be verified before the mission can start.", style = MaterialTheme.typography.bodySmall, color = TextSecondary)
                }
            }
            Spacer(Modifier.height(24.dp))

            checklist.forEachIndexed { index, item ->
                Row(
                    modifier = Modifier.fillMaxWidth().clickable { checklist[index] = item.copy(isChecked = !item.isChecked) }.padding(vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = if (item.isChecked) Icons.Default.CheckCircle else Icons.Outlined.Circle,
                        contentDescription = null,
                        tint = if (item.isChecked) AccentSage else TextTertiary,
                        modifier = Modifier.size(28.dp)
                    )
                    Spacer(Modifier.width(16.dp))
                    Text(text = item.text, style = MaterialTheme.typography.bodyLarge, color = if (item.isChecked) TextPrimary else TextSecondary)
                }
                if (index < checklist.size - 1) HorizontalDivider(color = LineColor)
            }
            
            Spacer(Modifier.weight(1f))
            
            Button(
                onClick = onStartMission,
                modifier = Modifier.fillMaxWidth().height(56.dp),
                enabled = allChecked,
                colors = ButtonDefaults.buttonColors(
                    containerColor = AccentSage,
                    contentColor = BgColor,
                    disabledContainerColor = LineColor,
                    disabledContentColor = TextTertiary
                )
            ) {
                Text("Start Mission", style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}
