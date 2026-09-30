package com.example.projectiknos.surveyor_field

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import com.example.projectiknos.api.RetrofitClient
import com.example.projectiknos.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FieldCommanderMissionScreen(
    missionId: String,
    onMissionComplete: (String) -> Unit,
    onAbort: () -> Unit,
    onBack: () -> Unit
) {
    val coroutineScope = rememberCoroutineScope()
    var commandStatus by remember { mutableStateOf("Drone waiting for command...") }
    var isCommanding by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Field Commander: Mission $missionId", style = MaterialTheme.typography.titleMedium, color = TextPrimary) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, "Back", tint = TextPrimary)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PanelColor)
            )
        },
        containerColor = BgColor
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // Map Placeholder
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .background(Color.Black),
                contentAlignment = Alignment.Center
            ) {
                Text("Field Commander Map View\n(Grid Pattern + Drone Tracking)", color = Color.Gray, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
            }

            // Command Control Panel
            Surface(
                color = PanelColor,
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Command Control", color = AccentBlue, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                    Spacer(modifier = Modifier.height(16.dp))
                    
                    Button(
                        onClick = {
                            isCommanding = true
                            commandStatus = "Command sent, waiting for Drone..."
                            coroutineScope.launch {
                                try {
                                    // Hit the real backend API!
                                    RetrofitClient.instance.triggerCaptureCommand()
                                    commandStatus = "Capture command received by backend!"
                                    
                                    // Auto advance after a few seconds for demo
                                    kotlinx.coroutines.delay(2000)
                                    onMissionComplete(missionId)
                                } catch (e: Exception) {
                                    commandStatus = "Error: ${e.message}"
                                } finally {
                                    isCommanding = false
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = AccentBlue),
                        enabled = !isCommanding
                    ) {
                        Text(if (isCommanding) "Commanding..." else "📸 Command Drone to Capture")
                    }
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(commandStatus, color = TextSecondary, fontSize = 12.sp, modifier = Modifier.align(Alignment.CenterHorizontally))
                    
                    Spacer(modifier = Modifier.height(16.dp))
                    OutlinedButton(
                        onClick = onAbort,
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentRust)
                    ) {
                        Text("Abort Mission")
                    }
                }
            }
        }
    }
}
