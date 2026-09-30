package com.example.projectiknos.surveyor_field

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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

data class ImageQcItem(val seq: Int, val qualityFlag: String, val blurScore: Float, val lat: Double, val lon: Double)

/**
 * Post-Flight QC Screen — SURVEYOR_DRONE role.
 *
 * Shows:
 *   - Total images, pass/blur counts, coverage estimate
 *   - List of blur-flagged images (for re-flight targeting)
 *   - Overall QC verdict: PASS or RE_FLIGHT_REQUIRED
 *
 * Design contracts:
 *   - Re-flight targeting is sector-based, NOT a full re-survey.
 *   - Coverage is an estimate based on image positions and spacing, NOT a legally
 *     precise photogrammetric result. ODM computes the real orthomosaic.
 *   - If blur_count / total > 20%, QC verdict is RE_FLIGHT_REQUIRED automatically.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PostFlightQCScreen(
    missionId: String,
    onPass: () -> Unit,
    onReflightRequired: (String) -> Unit,
    onBack: () -> Unit
) {
    var images by remember { mutableStateOf<List<ImageQcItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var verdict by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(missionId) {
        scope.launch {
            // In production: fetch from GET /missions/{mission_id}/images
            // Mocking QC data for MVP demonstration
            val mockData = (1..25).map { seq ->
                val score = if (seq % 7 == 0) 45f else (80f + seq * 1.5f)  // every 7th image blurred
                ImageQcItem(
                    seq = seq,
                    qualityFlag = if (score < 100f) "BLUR" else "PASS",
                    blurScore = score,
                    lat = 28.6139 + seq * 0.0001,
                    lon = 77.2090 + seq * 0.0001
                )
            }
            images = mockData
            val blurCount = mockData.count { it.qualityFlag == "BLUR" }
            val blurRate = blurCount.toFloat() / mockData.size
            verdict = if (blurRate > 0.20f) "RE_FLIGHT_REQUIRED" else "PASS"
            isLoading = false
        }
    }

    val passCount = images.count { it.qualityFlag == "PASS" }
    val blurCount = images.count { it.qualityFlag == "BLUR" }
    val total = images.size

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Post-Flight QC") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { padding ->
        if (isLoading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        } else {
            LazyColumn(Modifier.padding(padding).padding(horizontal = 16.dp)) {
                item {
                    Spacer(Modifier.height(12.dp))
                    // QC Summary card
                    val verdictColor = if (verdict == "PASS") Color(0xFF2E7D32) else Color(0xFFC62828)
                    Card(colors = CardDefaults.cardColors(containerColor = verdictColor.copy(alpha = 0.12f))) {
                        Column(Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    if (verdict == "PASS") Icons.Default.CheckCircle else Icons.Default.Warning,
                                    null, tint = verdictColor, modifier = Modifier.size(32.dp)
                                )
                                Spacer(Modifier.width(12.dp))
                                Column {
                                    Text(
                                        verdict ?: "—",
                                        fontWeight = FontWeight.Bold,
                                        color = verdictColor,
                                        style = MaterialTheme.typography.titleLarge
                                    )
                                    Text(
                                        if (verdict == "PASS") "Coverage meets quality threshold."
                                        else "Blur rate exceeds 20% — re-flight required for flagged sectors.",
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                            }
                        }
                    }
                    Spacer(Modifier.height(12.dp))

                    // Stats row
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        StatCard("Total", "$total", MaterialTheme.colorScheme.primary, Modifier.weight(1f))
                        StatCard("Pass", "$passCount", Color(0xFF2E7D32), Modifier.weight(1f))
                        StatCard("Blur", "$blurCount", Color(0xFFC62828), Modifier.weight(1f))
                    }
                    Spacer(Modifier.height(12.dp))

                    Text("Image Log", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(4.dp))
                }

                items(images) { img ->
                    val rowColor = if (img.qualityFlag == "BLUR") Color(0xFFFFEBEE) else MaterialTheme.colorScheme.surface
                    Card(
                        colors = CardDefaults.cardColors(containerColor = rowColor),
                        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp)
                    ) {
                        Row(Modifier.padding(8.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text("#${img.seq}", style = MaterialTheme.typography.labelMedium, modifier = Modifier.width(32.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(img.qualityFlag, fontWeight = FontWeight.SemiBold, color = if (img.qualityFlag == "BLUR") Color(0xFFC62828) else Color(0xFF2E7D32), modifier = Modifier.width(60.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Score: ${img.blurScore.toInt()}", style = MaterialTheme.typography.bodySmall)
                            Spacer(Modifier.weight(1f))
                            Text("${String.format("%.4f", img.lat)}, ${String.format("%.4f", img.lon)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }

                item {
                    Spacer(Modifier.height(16.dp))
                    when (verdict) {
                        "PASS" -> Button(onClick = onPass, modifier = Modifier.fillMaxWidth()) {
                            Icon(Icons.Default.CheckCircle, null)
                            Spacer(Modifier.width(8.dp))
                            Text("Confirm QC Pass")
                        }
                        "RE_FLIGHT_REQUIRED" -> {
                            val blurSector = "SECTOR_BLUR_${images.filter { it.qualityFlag == "BLUR" }.take(3).map { it.seq }.joinToString("-")}"
                            Button(
                                onClick = { onReflightRequired(blurSector) },
                                modifier = Modifier.fillMaxWidth(),
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFC62828))
                            ) {
                                Icon(Icons.Default.FlightTakeoff, null)
                                Spacer(Modifier.width(8.dp))
                                Text("Schedule Re-Flight")
                            }
                        }
                    }
                    Spacer(Modifier.height(32.dp))
                }
            }
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, color: Color, modifier: Modifier) {
    Card(colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.1f)), modifier = modifier) {
        Column(Modifier.padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(value, fontWeight = FontWeight.Bold, color = color, style = MaterialTheme.typography.titleLarge)
            Text(label, style = MaterialTheme.typography.labelSmall, color = color)
        }
    }
}
