package com.example.projectiknos.surveyor_drone

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import com.example.projectiknos.api.RetrofitClient
import com.example.projectiknos.api.Case
import com.example.projectiknos.ui.theme.*

/**
 * SCREEN 3.1 — Parcel Load & Verify (Drone, Step 1)
 *
 * Spec §3.1:
 *  - Shows parcel info + cadastral boundary
 *  - Adjust (vertex editing) / Approve (locks AOI, unlocks Step 2)
 *  - If NO cadastral geometry → Perimeter Walk mode (GPS breadcrumb trail)
 *
 * Step counter advances from backend mission state.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DroneParcelVerifyScreen(
    caseId: String,
    onApproved: (caseId: String) -> Unit,  // Unlocks Step 2
    onLogout: () -> Unit
) {
    var caseData by remember { mutableStateOf<Case?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var hasGeometry by remember { mutableStateOf(true) }  // populated from parcel check
    var errorMsg by remember { mutableStateOf<String?>(null) }
    var isApproving by remember { mutableStateOf(false) }
    var isAdjusting by remember { mutableStateOf(false) }
    var adjustConfirmNeeded by remember { mutableStateOf(false) }
    // Perimeter Walk state
    var perimeterWalkActive by remember { mutableStateOf(false) }
    var breadcrumbCount by remember { mutableIntStateOf(0) }
    var polygonClosed by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(caseId) {
        scope.launch {
            try {
                caseData = RetrofitClient.instance.getCase(caseId)
                // Check if parcel has geometry — in production parse parcel GeoJSON
                // For now: if parcel_id starts with 'X' → no geometry (demo trigger)
                hasGeometry = !caseData!!.parcel_id.startsWith("X")
                if (!hasGeometry) perimeterWalkActive = true
            } catch (e: Exception) {
                errorMsg = e.localizedMessage
            } finally {
                isLoading = false
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("SURVEYOR DRONE · Step 1: Parcel", style = MaterialTheme.typography.titleSmall, color = TextPrimary, fontFamily = FontFamily.Monospace)
                        caseData?.let { Text("Case ${it.case_id.take(8).uppercase()}", style = MaterialTheme.typography.labelSmall, color = TextSecondary) }
                    }
                },
                actions = {
                    // GPS status badge
                    Surface(color = AccentSage.copy(alpha = 0.15f), shape = MaterialTheme.shapes.small) {
                        Text("GPS 3D", color = AccentSage, fontSize = 11.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp))
                    }
                    Spacer(Modifier.width(8.dp))
                    // End Mission — always visible, always destructive
                    var showEndConfirm by remember { mutableStateOf(false) }
                    Button(
                        onClick = { showEndConfirm = true },
                        colors = ButtonDefaults.buttonColors(containerColor = AccentRust),
                        contentPadding = PaddingValues(horizontal = 12.dp)
                    ) { Text("End Mission", fontSize = 12.sp) }
                    if (showEndConfirm) {
                        AlertDialog(
                            onDismissRequest = { showEndConfirm = false },
                            title = { Text("End Mission?") },
                            text = { Text("This will abort the current mission. All unsaved progress will be lost.") },
                            confirmButton = { Button(onClick = onLogout, colors = ButtonDefaults.buttonColors(containerColor = AccentRust)) { Text("End Mission") } },
                            dismissButton = { TextButton(onClick = { showEndConfirm = false }) { Text("Cancel") } }
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PanelColor)
            )
        },
        // Drone Stepper — 5 steps, Step 1 active
        bottomBar = {
            DroneStepperBar(activeStep = 0)
        },
        containerColor = BgColor
    ) { padding ->
        when {
            isLoading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = AccentSlate)
            }
            errorMsg != null -> Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
                Text(errorMsg!!, color = AccentRust)
            }
            perimeterWalkActive && !hasGeometry -> {
                // PERIMETER WALK MODE — spec §3.1 edge case
                PerimeterWalkMode(
                    breadcrumbCount = breadcrumbCount,
                    polygonClosed = polygonClosed,
                    onAddPoint = { breadcrumbCount++ },
                    onClosePolygon = { polygonClosed = true },
                    onApprove = {
                        isApproving = true
                        scope.launch {
                            // Save perimeter walk as AOI, then advance
                            onApproved(caseId)
                        }
                    },
                    modifier = Modifier.padding(padding)
                )
            }
            else -> {
                // NORMAL VERIFY MODE — cadastral boundary shown
                Column(
                    modifier = Modifier
                        .padding(padding)
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                ) {
                    caseData?.let { case ->
                        // Parcel info card
                        Card(
                            modifier = Modifier.fillMaxWidth().padding(16.dp),
                            colors = CardDefaults.cardColors(containerColor = PanelColor)
                        ) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text("PARCEL INFORMATION", style = MaterialTheme.typography.labelMedium, color = TextSecondary, letterSpacing = 0.8.sp)
                                HorizontalDivider(color = LineColor)
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text("Parcel ID", color = TextSecondary, fontSize = 13.sp)
                                    Text(case.parcel_id, color = TextPrimary, fontWeight = FontWeight.Medium, fontFamily = FontFamily.Monospace, fontSize = 13.sp)
                                }
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text("Trigger Source", color = TextSecondary, fontSize = 13.sp)
                                    Text(case.action.replace("_", " ").uppercase(), color = AccentAmber, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                                }
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text("Status", color = TextSecondary, fontSize = 13.sp)
                                    Text(case.status.replace("_", " ").uppercase(), color = TextPrimary, fontSize = 13.sp)
                                }
                            }
                        }

                        // Map placeholder — cadastral boundary only
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(280.dp)
                                .padding(horizontal = 16.dp)
                                .background(Color(0xFF0D1B2A), MaterialTheme.shapes.medium),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("📍", fontSize = 32.sp)
                                Spacer(Modifier.height(8.dp))
                                Text("Cadastral Boundary Map", color = TextSecondary, fontSize = 14.sp)
                                Text("(Satellite tile + dashed boundary overlay)", color = TextTertiary, fontSize = 11.sp)
                                Spacer(Modifier.height(12.dp))
                                // Placeholder confidence badge if AI boundary available
                                Surface(color = AccentSage.copy(0.15f), shape = MaterialTheme.shapes.small) {
                                    Text("ML Boundary: ${case.confidence_score.toInt()}% confidence", color = AccentSage, fontSize = 11.sp, modifier = Modifier.padding(6.dp))
                                }
                            }
                        }

                        // Boundary Tool Actions
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(16.dp),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            OutlinedButton(
                                onClick = { isAdjusting = true; adjustConfirmNeeded = false },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentAmber)
                            ) { Text("Adjust") }

                            Button(
                                onClick = {
                                    isApproving = true
                                    scope.launch {
                                        // Approve locks AOI; next: step 2 unlocks
                                        onApproved(caseId)
                                    }
                                },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(containerColor = AccentSage),
                                enabled = !isApproving
                            ) {
                                if (isApproving) CircularProgressIndicator(Modifier.size(18.dp), color = Color.White, strokeWidth = 2.dp)
                                else Text("Approve →")
                            }
                        }

                        if (isAdjusting) {
                            Card(
                                Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                                colors = CardDefaults.cardColors(containerColor = AccentAmber.copy(0.08f))
                            ) {
                                Column(Modifier.padding(12.dp)) {
                                    Text("Vertex Editing Mode Active", color = AccentAmber, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                                    Text("Drag boundary vertices on the map to adjust. Save when done.", color = TextSecondary, fontSize = 12.sp, modifier = Modifier.padding(top = 4.dp))
                                    Spacer(Modifier.height(12.dp))
                                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        OutlinedButton(onClick = { isAdjusting = false }, modifier = Modifier.weight(1f)) { Text("Discard") }
                                        Button(
                                            onClick = { isAdjusting = false; adjustConfirmNeeded = true },
                                            modifier = Modifier.weight(1f)
                                        ) { Text("Save Adjustment") }
                                    }
                                }
                            }
                        }

                        if (adjustConfirmNeeded) {
                            Card(
                                Modifier.fillMaxWidth().padding(16.dp),
                                colors = CardDefaults.cardColors(containerColor = AccentSlate.copy(0.1f))
                            ) {
                                Text("Boundary adjusted. Review the corrected polygon above, then tap Approve to proceed.", color = TextSecondary, fontSize = 13.sp, modifier = Modifier.padding(12.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}

// Perimeter Walk mode (spec §3.1 edge case — no cadastral geometry)
@Composable
private fun PerimeterWalkMode(
    breadcrumbCount: Int,
    polygonClosed: Boolean,
    onAddPoint: () -> Unit,
    onClosePolygon: () -> Unit,
    onApprove: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        // Warning banner
        Surface(color = AccentAmber.copy(0.15f), shape = MaterialTheme.shapes.medium, modifier = Modifier.fillMaxWidth()) {
            Row(Modifier.padding(12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.LocationOn, null, tint = AccentAmber, modifier = Modifier.size(24.dp))
                Column {
                    Text("No Cadastral Geometry Found", color = AccentAmber, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    Text("Walk the boundary of this parcel. The GPS trail will define the survey area.", color = TextSecondary, fontSize = 12.sp)
                }
            }
        }

        // Map breadcrumb placeholder
        Box(
            modifier = Modifier.fillMaxWidth().height(300.dp).background(Color(0xFF0D1B2A), MaterialTheme.shapes.medium),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("🗺️", fontSize = 36.sp)
                Spacer(Modifier.height(8.dp))
                Text("GPS Breadcrumb Trail", color = TextSecondary, fontSize = 14.sp)
                Text("$breadcrumbCount points recorded", color = if (breadcrumbCount > 3) AccentSage else AccentAmber, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                if (polygonClosed) {
                    Spacer(Modifier.height(8.dp))
                    Surface(color = AccentSage.copy(0.2f), shape = MaterialTheme.shapes.small) {
                        Text("Polygon closed ✓", color = AccentSage, fontSize = 12.sp, modifier = Modifier.padding(6.dp))
                    }
                }
            }
        }

        // Controls
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(
                onClick = onAddPoint,
                modifier = Modifier.weight(1f),
                enabled = !polygonClosed
            ) { Text("Record Point") }

            Button(
                onClick = onClosePolygon,
                modifier = Modifier.weight(1f),
                enabled = breadcrumbCount >= 3 && !polygonClosed,
                colors = ButtonDefaults.buttonColors(containerColor = AccentAmber)
            ) { Text("Close Polygon") }
        }

        Button(
            onClick = onApprove,
            modifier = Modifier.fillMaxWidth(),
            enabled = polygonClosed,
            colors = ButtonDefaults.buttonColors(containerColor = AccentSage)
        ) { Text("Approve Perimeter Walk AOI →") }
    }
}

// ---- Shared Drone Stepper Bottom Bar ----
@Composable
fun DroneStepperBar(activeStep: Int) {
    val steps = listOf("Parcel", "Plan", "Fly", "Capture", "Process")
    Surface(color = PanelColor) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            steps.forEachIndexed { i, label ->
                val isDone = i < activeStep
                val isActive = i == activeStep
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.weight(1f)) {
                    Surface(
                        shape = MaterialTheme.shapes.small,
                        color = when {
                            isActive -> AccentSlate
                            isDone -> AccentSage.copy(0.3f)
                            else -> Color(0xFF1E293B)
                        }
                    ) {
                        Text(
                            if (isDone) "✓" else "${i + 1}",
                            color = when {
                                isActive -> Color.White
                                isDone -> AccentSage
                                else -> TextTertiary
                            },
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                    Text(label, fontSize = 9.sp, color = if (isActive) TextPrimary else TextTertiary, modifier = Modifier.padding(top = 2.dp))
                }
            }
        }
    }
}
