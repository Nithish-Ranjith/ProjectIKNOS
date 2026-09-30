package com.example.projectiknos.surveyor_drone

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import com.example.projectiknos.ui.theme.*

/**
 * SCREEN 3.5 — Process (Stitch & Analyze)
 * Spec §3.5: Job status list — Upload, Photogrammetry, Boundary Extraction,
 *            Spatial Comparison, Evidence Fusion. Each stage has its own state.
 * Uses simulated ODM progress (fake timers) per approved plan.
 */
private enum class JobState { QUEUED, RUNNING, DONE, FAILED }

private data class PipelineJob(
    val name: String,
    val description: String,
    var state: JobState = JobState.QUEUED,
    var failReason: String? = null
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MissionProcessScreen(
    missionId: String,
    onDone: () -> Unit,
    onBack: () -> Unit
) {
    val jobs = remember {
        mutableStateListOf(
            PipelineJob("Upload", "Transferring captured images to server"),
            PipelineJob("Photogrammetry", "OpenDroneMap 3D reconstruction"),
            PipelineJob("Boundary Extraction", "Detecting parcel boundary from orthophoto"),
            PipelineJob("Spatial Comparison", "Computing IoU, Hausdorff, ΔArea vs. cadastral"),
            PipelineJob("Evidence Fusion", "Merging temporal, spatial & records evidence")
        )
    }
    var allDone by remember { mutableStateOf(false) }
    var anyFailed by remember { mutableStateOf(false) }
    var resultConfidenceScore by remember { mutableStateOf(0f) }

    // Simulate pipeline progression
    LaunchedEffect(missionId) {
        val durations = listOf(1200L, 3000L, 2000L, 1500L, 1000L)
        jobs.forEachIndexed { i, job ->
            jobs[i] = job.copy(state = JobState.RUNNING)
            delay(durations[i])
            // Simulate occasional failure on photogrammetry if missionId ends in 'F'
            if (i == 1 && missionId.endsWith("F", ignoreCase = true)) {
                jobs[i] = job.copy(state = JobState.FAILED, failReason = "Reconstruction failed — insufficient image overlap in Block 4")
                anyFailed = true
                return@LaunchedEffect  // Stop pipeline on failure
            }
            jobs[i] = job.copy(state = JobState.DONE)
        }
        resultConfidenceScore = 88.0f
        allDone = true
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Step 5: Process & Analyze", color = TextPrimary) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PanelColor)
            )
        },
        bottomBar = { DroneStepperBar(activeStep = 4) },
        containerColor = BgColor
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text("PROCESSING PIPELINE", style = MaterialTheme.typography.labelMedium, color = TextSecondary, letterSpacing = 0.8.sp)

            jobs.forEachIndexed { index, job ->
                JobStatusRow(job = job)
            }

            // Failure card with re-fly path (spec §3.5 edge case)
            if (anyFailed) {
                val failedJob = jobs.firstOrNull { it.state == JobState.FAILED }
                Spacer(Modifier.height(8.dp))
                Card(
                    colors = CardDefaults.cardColors(containerColor = AccentRust.copy(0.1f)),
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Pipeline Failed", color = AccentRust, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Text(
                            failedJob?.failReason ?: "Unknown error",
                            color = TextSecondary,
                            fontSize = 13.sp
                        )
                        Button(
                            onClick = onBack,  // Navigate back to Step 4 for re-fly
                            colors = ButtonDefaults.buttonColors(containerColor = AccentRust),
                            modifier = Modifier.fillMaxWidth()
                        ) { Text("→ Return to Step 4 for Re-fly") }
                    }
                }
            }

            // Success result card (spec §3.5)
            if (allDone) {
                Spacer(Modifier.height(8.dp))
                Card(
                    colors = CardDefaults.cardColors(containerColor = AccentSage.copy(0.1f)),
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Analysis Complete", color = AccentSage, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        HorizontalDivider(color = LineColor)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Confidence Score", color = TextSecondary, fontSize = 13.sp)
                            // Score bounded 0-100, never out-of-range (spec §3.5)
                            val bounded = resultConfidenceScore.coerceIn(0f, 100f)
                            Text("${bounded.toInt()} / 100", color = AccentSage, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Case Status", color = TextSecondary, fontSize = 13.sp)
                            Text("FIELD VERIFICATION REQUIRED", color = AccentAmber, fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
                        }
                        Spacer(Modifier.height(8.dp))
                        Button(
                            onClick = onDone,
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = AccentSlate)
                        ) { Text("Done — Mission Complete") }
                    }
                }
            }
        }
    }
}

@Composable
private fun JobStatusRow(job: PipelineJob) {
    val (icon, color) = when (job.state) {
        JobState.QUEUED -> "○" to TextTertiary
        JobState.RUNNING -> "⟳" to AccentAmber
        JobState.DONE -> "✓" to AccentSage
        JobState.FAILED -> "✗" to AccentRust
    }

    Card(
        colors = CardDefaults.cardColors(containerColor = PanelColor),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            if (job.state == JobState.RUNNING) {
                CircularProgressIndicator(Modifier.size(20.dp), color = AccentAmber, strokeWidth = 2.dp)
            } else {
                Text(icon, color = color, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            }
            Column(Modifier.weight(1f)) {
                Text(job.name, color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                Text(job.description, color = TextSecondary, fontSize = 11.sp)
                job.failReason?.let {
                    Text(it, color = AccentRust, fontSize = 11.sp, modifier = Modifier.padding(top = 2.dp))
                }
            }
            Surface(
                color = color.copy(alpha = 0.12f),
                shape = MaterialTheme.shapes.small
            ) {
                Text(job.state.name, color = color, fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
            }
        }
    }
}
