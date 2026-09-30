package com.example.projectiknos.customer

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import com.example.projectiknos.api.RetrofitClient
import com.example.projectiknos.api.Case
import com.example.projectiknos.ui.components.*
import com.example.projectiknos.ui.theme.*

/**
 * Customer Home — My Parcels.
 * Role: CUSTOMER (tier 0).
 *
 * Improvements:
 *  - New desaturated palette — no neon, no raw hex
 *  - Greeting header (Feature C3 — plain language)
 *  - Bottom navigation bar
 *  - Parcel timeline strip on each card (Feature C1)
 *  - StatusPill (semantic color chip, not raw amber literal)
 *  - SkeletonCardList loading state
 *  - Notification badge on nav (Feature C2 stub)
 *  - Raw confidence_score never shown — design contract preserved
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomerHomeScreen(onFileObjection: (String) -> Unit, onLogout: () -> Unit) {
    var cases        by remember { mutableStateOf<List<Case>>(emptyList()) }
    var isLoading    by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var selectedNav  by remember { mutableIntStateOf(0) }
    val coroutineScope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        coroutineScope.launch {
            try {
                // Use /my-cases — scoped to this customer's parcels, never /cases (403)
                cases = RetrofitClient.instance.getMyCases()
            } catch (e: Exception) {
                errorMessage = "Could not load parcel status: ${e.localizedMessage}"
            } finally {
                isLoading = false
            }
        }
    }

    IknosTheme {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("My Parcels", style = MaterialTheme.typography.titleMedium, color = TextPrimary) },
                    actions = {
                        TextButton(onClick = onLogout) {
                            Text("Logout", color = TextSecondary, fontSize = 13.sp)
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = PanelColor)
                )
            },
            bottomBar = {
                NavigationBar(containerColor = PanelColor) {
                    NavigationBarItem(
                        selected = selectedNav == 0,
                        onClick = { selectedNav = 0 },
                        icon = { Icon(Icons.Default.Home, null) },
                        label = { Text("Parcels") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = AccentSlate,
                            selectedTextColor = AccentSlate,
                            unselectedIconColor = TextSecondary,
                            unselectedTextColor = TextSecondary,
                            indicatorColor = AccentSlate.copy(alpha = 0.12f)
                        )
                    )
                    NavigationBarItem(
                        selected = selectedNav == 1,
                        onClick = { selectedNav = 1 },
                        icon = {
                            BadgedBox(badge = {
                                if (cases.any { it.status == "open" || it.status == "field_verification" }) {
                                    Badge(containerColor = AccentAmber) {
                                        Text("!", fontSize = 9.sp)
                                    }
                                }
                            }) {
                                Icon(Icons.Default.Notifications, null)
                            }
                        },
                        label = { Text("Alerts") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = AccentSlate,
                            selectedTextColor = AccentSlate,
                            unselectedIconColor = TextSecondary,
                            unselectedTextColor = TextSecondary,
                            indicatorColor = AccentSlate.copy(alpha = 0.12f)
                        )
                    )
                    NavigationBarItem(
                        selected = selectedNav == 2,
                        onClick = { selectedNav = 2 },
                        icon = { Icon(Icons.Default.Person, null) },
                        label = { Text("Profile") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = AccentSlate,
                            selectedTextColor = AccentSlate,
                            unselectedIconColor = TextSecondary,
                            unselectedTextColor = TextSecondary,
                            indicatorColor = AccentSlate.copy(alpha = 0.12f)
                        )
                    )
                }
            },
            containerColor = BgColor
        ) { padding ->
            when {
                isLoading -> {
                    SkeletonCardList(
                        count = 4,
                        modifier = Modifier
                            .padding(padding)
                            .padding(horizontal = 16.dp, vertical = 12.dp)
                    )
                }
                errorMessage != null -> {
                    Box(
                        Modifier.fillMaxSize().padding(24.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(errorMessage!!, color = AccentRust, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                else -> {
                    LazyColumn(
                        Modifier.padding(padding).padding(horizontal = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        // Greeting header — plain language (Feature C3)
                        item {
                            Spacer(Modifier.height(4.dp))
                            Column(Modifier.padding(vertical = 6.dp)) {
                                Text(
                                    "Good morning 👋",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary
                                )
                                Text(
                                    "${cases.size} parcel(s) registered",
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }

                        if (cases.isEmpty()) {
                            item {
                                Box(
                                    Modifier.fillMaxWidth().height(240.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text("🌾", fontSize = 48.sp)
                                        Spacer(Modifier.height(12.dp))
                                        Text(
                                            "No parcels linked to this number yet",
                                            color = TextSecondary,
                                            style = MaterialTheme.typography.bodyMedium
                                        )
                                        Spacer(Modifier.height(16.dp))
                                        Button(
                                            onClick = { /* TODO: navigate to LinkParcelScreen */ },
                                            colors = ButtonDefaults.buttonColors(containerColor = AccentSlate)
                                        ) { Text("Link a parcel") }
                                    }
                                }
                            }
                        } else {
                            items(cases) { case ->
                                ParcelStatusCard(case = case, onFileObjection = onFileObjection)
                            }
                        }
                        item { Spacer(Modifier.height(8.dp)) }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Parcel card for Customer role
// ---------------------------------------------------------------------------

@Composable
fun ParcelStatusCard(case: Case, onFileObjection: (String) -> Unit) {
    // Plain-language status mapping — NEVER shows confidence_score to customer
    val (friendlyStatus, statusKey) = when (case.status) {
        "open"                -> "Under Review" to "open"
        "field_verification"  -> "Field Visit Scheduled" to "field_verification"
        "authority_review"    -> "Senior Officer Review" to "authority_review"
        "closed"              -> "No Issues Found" to "closed"
        "rejected"            -> "Action Required" to "rejected"
        else                  -> case.status.replace("_", " ") to case.status
    }

    // Timeline stages for this parcel (Feature C1)
    val timelineStages = listOf(
        TimelineStage("Submitted",  "📋", "Sep 1",  isComplete = true),
        TimelineStage("Survey",     "🚁", "Sep 5",  isComplete = true),
        TimelineStage("Processing", "⚙",  "Sep 8",  isComplete = case.status != "open"),
        TimelineStage("Review",     "👁",  null,    isComplete = false, isActive = case.status == "field_verification"),
        TimelineStage("Outcome",    "✅",  null,    isComplete = case.status == "closed")
    )

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = PanelColor),
        shape = MaterialTheme.shapes.medium
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {

            // Header row: parcel ID + status pill
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            case.parcel_id,
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.titleSmall
                        )
                        // G3: Flag shown only when score stored as percentage >= 90 (i.e. high discrepancy)
                        // confidence_score is stored as 0-100 (e.g. 88.0 = 88%)
                        if (case.confidence_score >= 90f) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("🚩", fontSize = 14.sp)
                        }
                    }
                    Text(
                        "Survey reference: ${case.case_id.take(6).uppercase()}",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextSecondary
                    )
                }
                StatusPill(status = statusKey)
            }

            // Plain-language summary
            Text(
                buildPlainSummary(case.status),
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )

            HorizontalDivider(color = LineColor)

            // Timeline strip (Feature C1)
            Text(
                "CASE PROGRESS",
                style = MaterialTheme.typography.labelSmall,
                color = TextTertiary,
                letterSpacing = 0.8.sp
            )
            ParcelTimeline(stages = timelineStages)

            // 'Raise a concern' — always present per spec §1.2
            OutlinedButton(
                onClick = { onFileObjection(case.parcel_id) },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentSlate)
            ) {
                Text("Raise a concern", fontWeight = FontWeight.Medium)
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Plain-language summary (Feature C3) — never exposes internal scores
// ---------------------------------------------------------------------------

// Plain-language status copy per spec §1.2 — exact wording required
private fun buildPlainSummary(status: String): String = when (status) {
    "open"                          -> "We found something that needs a closer look. A field officer will visit your parcel."
    "field_verification_required"   -> "We found something that needs a closer look. A field officer will visit your parcel."
    "field_verification"            -> "A field visit has happened. An officer is reviewing the findings."
    "officer_review_pending"        -> "A field visit has happened. An officer is reviewing the findings."
    "authority_review"              -> "A field visit has happened. An officer is reviewing the findings."
    "closed"                        -> "Review complete — no changes needed."
    "rejected"                      -> "Review complete — no changes needed."
    "approved"                      -> "Your land record has been updated. See details below."
    else                            -> "No review currently in progress."
}
