package com.example.projectiknos.customer

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.FlightTakeoff
import androidx.compose.material.icons.filled.Gavel
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.PendingActions
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.projectiknos.ui.theme.*

data class TimelineStage(
    val title: String,
    val description: String,
    val date: String?,
    val isCompleted: Boolean,
    val isCurrent: Boolean,
    val icon: ImageVector
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ParcelTimelineScreen(parcelId: String, onBack: () -> Unit) {
    val stages = listOf(
        TimelineStage("Survey Initiated", "Cadastral records pulled from central database.", "Oct 10, 2023", true, false, Icons.Default.Map),
        TimelineStage("Drone Flight", "High-resolution aerial imagery captured.", "Oct 12, 2023", true, false, Icons.Default.FlightTakeoff),
        TimelineStage("Processing", "AI boundary extraction and discrepancy check.", "Oct 13, 2023", true, false, Icons.Default.PendingActions),
        TimelineStage("Field Review", "Surveyor field visit to verify boundaries.", "Pending", false, true, Icons.Default.CheckCircle),
        TimelineStage("Final Outcome", "Legal determination and mutation update.", null, false, false, Icons.Default.Gavel)
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Parcel Timeline") },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, contentDescription = "Back") }
                }
            )
        }
    ) { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)
        ) {
            Text(
                text = "Parcel $parcelId",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(24.dp))
            
            stages.forEachIndexed { index, stage ->
                TimelineNode(stage = stage, isLast = index == stages.size - 1)
            }
        }
    }
}

@Composable
fun TimelineNode(stage: TimelineStage, isLast: Boolean) {
    Row(modifier = Modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.width(40.dp)) {
            val iconColor = when {
                stage.isCompleted -> AccentSage
                stage.isCurrent -> AccentAmber
                else -> TextTertiary
            }
            Icon(imageVector = stage.icon, contentDescription = null, tint = iconColor, modifier = Modifier.size(24.dp))
            if (!isLast) {
                Canvas(modifier = Modifier.width(2.dp).weight(1f).padding(vertical = 4.dp)) {
                    val lineColor = if (stage.isCompleted) AccentSage else LineColor
                    drawLine(color = lineColor, start = Offset(size.width / 2, 0f), end = Offset(size.width / 2, size.height), strokeWidth = size.width)
                }
            } else {
                Spacer(modifier = Modifier.weight(1f))
            }
        }
        
        Column(modifier = Modifier.weight(1f).padding(bottom = 32.dp, start = 16.dp)) {
            val titleColor = if (stage.isCompleted || stage.isCurrent) TextPrimary else TextTertiary
            Text(text = stage.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = titleColor)
            Spacer(modifier = Modifier.height(4.dp))
            Text(text = stage.description, style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
            if (stage.date != null) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(text = stage.date, style = MaterialTheme.typography.labelSmall, color = AccentSlateLight)
            }
        }
    }
}
