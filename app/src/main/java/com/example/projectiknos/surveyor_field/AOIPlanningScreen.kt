package com.example.projectiknos.surveyor_field

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.FlightTakeoff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.projectiknos.ui.components.*
import com.example.projectiknos.ui.theme.*
import com.example.projectiknos.surveyor_drone.CameraConfig
import com.example.projectiknos.surveyor_drone.GridConfig
import com.example.projectiknos.surveyor_drone.GridMath

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AOIPlanningScreen(
    caseId: String,
    onNavigateToMission: (String, String) -> Unit,
    onBack: () -> Unit
) {
    // Static dummy polygon for demo (roughly matches the HTML shape)
    val cadastralPoly = listOf(
        560.0 to 190.0, 760.0 to 255.0, 845.0 to 430.0, 905.0 to 545.0, 
        810.0 to 690.0, 600.0 to 705.0, 500.0 to 650.0, 430.0 to 530.0, 440.0 to 350.0
    )
    val adjustedPoly = listOf(
        572.0 to 205.0, 748.0 to 262.0, 838.0 to 432.0, 892.0 to 540.0, 
        805.0 to 680.0, 605.0 to 692.0, 512.0 to 642.0, 442.0 to 528.0, 452.0 to 355.0
    )

    var altitude by remember { mutableStateOf("62.0") }
    var sideOverlap by remember { mutableStateOf("70.0") }
    var showCadastral by remember { mutableStateOf(true) }
    var showAdjusted by remember { mutableStateOf(true) }
    var showGrid by remember { mutableStateOf(true) }
    var showBlocks by remember { mutableStateOf(true) }

    val altM = altitude.toDoubleOrNull() ?: 62.0
    val soPct = sideOverlap.toDoubleOrNull() ?: 70.0
    val cam = CameraConfig(62.2, altM, 0.80, soPct / 100.0)
    val gridCfg = GridConfig(3, 3)

    val gridResult = remember(altM, soPct) {
        GridMath.computeGrid(adjustedPoly, 4.05, gridCfg, cam)
    }

    IknosTheme {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("AOI Planning — Case #$caseId", color = TextColor) },
                    navigationIcon = {
                        IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back", tint = TextColor) }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = PanelColor)
                )
            },
            containerColor = BgColor
        ) { padding ->
            Column(Modifier.padding(padding).padding(16.dp)) {
                
                DroneStepper(currentStep = 2, onStepClick = {})
                Spacer(modifier = Modifier.height(16.dp))

                Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    // LEFT COLUMN
                    Column(Modifier.weight(0.25f)) {
                        Panel("Parcel Information") {
                            KeyValueRow("Parcel ID", "AP-07107-...")
                            KeyValueRow("Village", "Rangapur")
                            KeyValueRow("Area (Cadastral)", "4.05 ha")
                            KeyValueRow("Area (Adjusted)", "4.12 ha")
                            Spacer(Modifier.height(8.dp))
                            Text("✓ Boundary Approved", color = AccentGreen, style = MaterialTheme.typography.labelSmall)
                        }
                        Spacer(Modifier.height(12.dp))
                        Panel("Layers") {
                            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                Checkbox(checked = showCadastral, onCheckedChange = { showCadastral = it })
                                Text("Cadastral Map", color = TextColor, fontSize = 13.sp)
                            }
                            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                Checkbox(checked = showAdjusted, onCheckedChange = { showAdjusted = it })
                                Text("Adjusted Boundary", color = TextColor, fontSize = 13.sp)
                            }
                            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                Checkbox(checked = showGrid, onCheckedChange = { showGrid = it })
                                Text("Grid Plan", color = TextColor, fontSize = 13.sp)
                            }
                            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                Checkbox(checked = showBlocks, onCheckedChange = { showBlocks = it })
                                Text("Parcel Blocks", color = TextColor, fontSize = 13.sp)
                            }
                        }
                    }

                    // CENTER MAP
                    Column(Modifier.weight(0.5f)) {
                        TacticalMap(
                            modifier = Modifier.weight(1f),
                            cadastralPoly = cadastralPoly,
                            adjustedPoly = adjustedPoly,
                            blocks = gridResult.blocks,
                            dronePos = null,
                            flightTrail = null,
                            showCadastral = showCadastral,
                            showAdjusted = showAdjusted,
                            showGrid = showGrid,
                            showBlocks = showBlocks
                        )
                    }

                    // RIGHT COLUMN
                    Column(Modifier.weight(0.25f)) {
                        Panel("Lawnmower Plan") {
                            val totalLines = gridResult.blocks.sumOf { it.lines.size }
                            val totalPoints = gridResult.blocks.sumOf { it.photoPoints.size }
                            
                            KeyValueRow("Total Blocks", "${gridResult.blocks.size}")
                            KeyValueRow("Photo Points", "$totalPoints")
                            KeyValueRow("Flight Lines", "$totalLines")
                            KeyValueRow("Coverage (Est.)", "98%", AccentGreen)
                            Spacer(Modifier.height(16.dp))
                            
                            OutlinedTextField(
                                value = altitude,
                                onValueChange = { altitude = it },
                                label = { Text("Altitude (m)", color = MutedColor) },
                                textStyle = androidx.compose.ui.text.TextStyle(color = TextColor)
                            )
                            Spacer(Modifier.height(8.dp))
                            OutlinedTextField(
                                value = sideOverlap,
                                onValueChange = { sideOverlap = it },
                                label = { Text("Side Overlap %", color = MutedColor) },
                                textStyle = androidx.compose.ui.text.TextStyle(color = TextColor)
                            )
                            
                            Spacer(Modifier.height(24.dp))
                            Button(
                                onClick = { 
                                    val aoiJson = adjustedPoly.joinToString(",", "[", "]") { "[${it.second},${it.first}]" }
                                    onNavigateToMission(caseId, aoiJson)
                                },
                                modifier = Modifier.fillMaxWidth(),
                                colors = ButtonDefaults.buttonColors(containerColor = AccentBlue)
                            ) {
                                Icon(Icons.Default.FlightTakeoff, null)
                                Spacer(Modifier.width(8.dp))
                                Text("Accept & Fly", fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }
        }
    }
}
