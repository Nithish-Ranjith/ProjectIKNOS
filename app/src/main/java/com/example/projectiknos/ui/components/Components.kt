package com.example.projectiknos.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.projectiknos.ui.theme.*

// ---------------------------------------------------------------------------
// Stepper data (Drone mission flow)
// ---------------------------------------------------------------------------

data class StepItem(val id: Int, val title: String, val subtitle: String)

val DroneSteps = listOf(
    StepItem(1, "Parcel",   "Load & Verify"),
    StepItem(2, "Plan",     "Split & Optimize"),
    StepItem(3, "Fly",      "Live Guidance"),
    StepItem(4, "Capture",  "Coverage & QC"),
    StepItem(5, "Process",  "Stitch & Analyze")
)

@Composable
fun DroneStepper(currentStep: Int, onStepClick: (Int) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(60.dp)
            .background(PanelColor, RoundedCornerShape(10.dp))
            .border(1.dp, LineColor, RoundedCornerShape(10.dp))
            .padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceEvenly
    ) {
        DroneSteps.forEach { step ->
            val isActive = step.id == currentStep
            val isDone   = step.id < currentStep
            Row(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable { onStepClick(step.id) }
                    .background(
                        when {
                            isActive -> AccentSlate.copy(alpha = 0.15f)
                            isDone   -> AccentSage.copy(alpha = 0.08f)
                            else     -> Color.Transparent
                        }
                    )
                    .border(
                        1.dp,
                        when {
                            isActive -> AccentSlate
                            isDone   -> AccentSage.copy(alpha = 0.4f)
                            else     -> Color.Transparent
                        },
                        RoundedCornerShape(8.dp)
                    )
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(24.dp)
                        .background(
                            when {
                                isActive -> AccentSlate
                                isDone   -> AccentSage
                                else     -> LineColor
                            },
                            CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = if (isDone) "✓" else step.id.toString(),
                        color = if (isActive || isDone) Color.White else TextSecondary,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
                Spacer(Modifier.width(7.dp))
                Column {
                    Text(
                        step.title,
                        color = if (isActive) TextPrimary else TextSecondary,
                        fontSize = 13.sp,
                        fontWeight = if (isActive) FontWeight.SemiBold else FontWeight.Normal
                    )
                    Text(step.subtitle, color = TextTertiary, fontSize = 10.sp)
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Panel — generic content container
// ---------------------------------------------------------------------------

@Composable
fun Panel(title: String? = null, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(PanelColor, RoundedCornerShape(10.dp))
            .border(1.dp, LineColor, RoundedCornerShape(10.dp))
            .padding(14.dp)
    ) {
        if (title != null) {
            Text(
                title.uppercase(),
                color = TextSecondary,
                fontSize = 10.sp,
                fontWeight = FontWeight.SemiBold,
                letterSpacing = 0.8.sp,
                modifier = Modifier.padding(bottom = 10.dp)
            )
        }
        content()
    }
}

// ---------------------------------------------------------------------------
// KeyValueRow — two-column label + value
// ---------------------------------------------------------------------------

@Composable
fun KeyValueRow(k: String, v: String, valueColor: Color = TextPrimary) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(k, color = TextSecondary, fontSize = 12.sp)
        Text(
            v,
            color = valueColor,
            fontFamily = FontFamily.Monospace,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium
        )
    }
}

// ---------------------------------------------------------------------------
// SeverityBadge — score number with HIGH / MEDIUM / LOW label below
// ---------------------------------------------------------------------------

@Composable
fun SeverityBadge(score: Int, modifier: Modifier = Modifier) {
    val bgColor = when {
        score >= 75 -> ScoreHigh
        score >= 50 -> ScoreMedium
        else        -> ScoreLow
    }
    val label = when {
        score >= 75 -> "HIGH"
        score >= 50 -> "MEDIUM"
        else        -> "LOW"
    }
    Column(
        modifier = modifier
            .background(bgColor, RoundedCornerShape(8.dp))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            "$score",
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 22.sp,
            fontFamily = FontFamily.Monospace
        )
        Text(
            label,
            color = Color.White.copy(alpha = 0.85f),
            fontSize = 9.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 0.5.sp
        )
    }
}

// ---------------------------------------------------------------------------
// StatusPill — colored chip for case.status
// ---------------------------------------------------------------------------

@Composable
fun StatusPill(status: String, modifier: Modifier = Modifier) {
    val (bg, fg, label) = when (status.lowercase()) {
        "open"                -> Triple(StatusOpen.copy(alpha = 0.15f),   StatusOpen,    "OPEN")
        "field_verification"  -> Triple(StatusReview.copy(alpha = 0.15f), StatusReview,  "IN REVIEW")
        "authority_review"    -> Triple(StatusReview.copy(alpha = 0.15f), StatusReview,  "AUTHORITY")
        "closed"              -> Triple(StatusClear.copy(alpha = 0.15f),  StatusClear,   "CLOSED")
        "rejected"            -> Triple(StatusConflict.copy(alpha=0.15f), StatusConflict,"REJECTED")
        else                  -> Triple(LineColor, TextSecondary, status.uppercase())
    }
    Box(
        modifier = modifier
            .background(bg, RoundedCornerShape(20.dp))
            .border(1.dp, fg.copy(alpha = 0.35f), RoundedCornerShape(20.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp)
    ) {
        Text(
            label,
            color = fg,
            fontSize = 10.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 0.5.sp
        )
    }
}

// ---------------------------------------------------------------------------
// OfflineBanner — shown when Room cache is being used instead of live API
// ---------------------------------------------------------------------------

@Composable
fun OfflineBanner(syncPending: Int = 0, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(AccentAmber.copy(alpha = 0.12f))
            .border(1.dp, AccentAmber.copy(alpha = 0.3f))
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text("⚠", fontSize = 14.sp, color = AccentAmber)
        Text(
            if (syncPending > 0)
                "Offline — $syncPending decision(s) queued for sync"
            else
                "Offline — showing cached data",
            color = AccentAmber,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium
        )
    }
}

// ---------------------------------------------------------------------------
// SkeletonLoader — replaces CircularProgressIndicator while loading lists
// ---------------------------------------------------------------------------

@Composable
fun SkeletonCardList(count: Int = 4, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        repeat(count) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(PanelColor, RoundedCornerShape(10.dp))
                    .padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Score badge skeleton
                Box(
                    modifier = Modifier
                        .size(52.dp)
                        .background(SurfaceOverlay, RoundedCornerShape(8.dp))
                )
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(Modifier.fillMaxWidth(0.6f).height(13.dp).background(SurfaceOverlay, RoundedCornerShape(4.dp)))
                    Box(Modifier.fillMaxWidth(0.4f).height(10.dp).background(SurfaceOverlay.copy(alpha = 0.6f), RoundedCornerShape(4.dp)))
                    Box(Modifier.fillMaxWidth(0.3f).height(9.dp).background(SurfaceOverlay.copy(alpha = 0.4f), RoundedCornerShape(4.dp)))
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// ParcelTimeline — horizontal stage strip for Customer role (Feature C1)
// ---------------------------------------------------------------------------

data class TimelineStage(
    val label: String,
    val icon: String,
    val date: String?,
    val isComplete: Boolean,
    val isActive: Boolean = false
)

@Composable
fun ParcelTimeline(stages: List<TimelineStage>, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top
    ) {
        stages.forEachIndexed { idx, stage ->
            // Connector line between stages
            if (idx > 0) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(2.dp)
                        .align(Alignment.Top)
                        .padding(top = 14.dp)
                        .background(if (stage.isComplete) AccentSage else LineColor)
                )
            }
            // Stage node
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.padding(horizontal = 2.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(28.dp)
                        .background(
                            when {
                                stage.isActive   -> AccentSlate
                                stage.isComplete -> AccentSage
                                else             -> LineColor
                            },
                            CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Text(stage.icon, fontSize = 13.sp)
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    stage.label,
                    color = if (stage.isActive) TextPrimary else TextSecondary,
                    fontSize = 9.sp,
                    fontWeight = if (stage.isActive) FontWeight.SemiBold else FontWeight.Normal
                )
                if (stage.date != null) {
                    Text(stage.date, color = TextTertiary, fontSize = 8.sp)
                }
            }
        }
    }
}
