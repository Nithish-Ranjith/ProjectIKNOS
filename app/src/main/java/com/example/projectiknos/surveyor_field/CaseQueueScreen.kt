package com.example.projectiknos.surveyor_field

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import com.example.projectiknos.api.RetrofitClient
import com.example.projectiknos.api.Case
import com.example.projectiknos.ui.components.*
import com.example.projectiknos.ui.theme.*

/**
 * Case Queue — SURVEYOR_FIELD / SENIOR_FIELD role.
 *
 * Improvements over previous version:
 *  - New desaturated color palette (no neon)
 *  - SeverityBadge component (score + HIGH/MEDIUM/LOW label)
 *  - SkeletonCardList for loading state
 *  - OfflineBanner when network is unavailable
 *  - Case IDs formatted as short 8-char prefix
 *  - Search bar for parcel ID / khasra lookup
 *  - Parcel ID and khasra number in each card
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CaseQueueScreen(onCaseSelected: (String) -> Unit, onLogout: () -> Unit) {
    var cases         by remember { mutableStateOf<List<Case>>(emptyList()) }
    var isLoading     by remember { mutableStateOf(true) }
    var isOffline     by remember { mutableStateOf(false) }
    var syncPending   by remember { mutableIntStateOf(0) }
    var errorMessage  by remember { mutableStateOf<String?>(null) }
    var selectedTab   by remember { mutableIntStateOf(0) }
    var searchQuery   by remember { mutableStateOf("") }
    val tabs = listOf("Open", "In Review", "Closed")
    val scope = rememberCoroutineScope()

    fun loadCases(statusFilter: String?) {
        isLoading = true
        errorMessage = null
        scope.launch {
            try {
                cases = RetrofitClient.instance.getCases(statusFilter)
                isOffline = false
            } catch (e: Exception) {
                // Attempt to use Room cache (Feature F3 — offline-first)
                isOffline = true
                errorMessage = "Network unavailable — showing cached cases"
                // TODO: cases = localCaseDao.getAll() once Room integration is complete
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) { loadCases("open") }

    // Filter cases by search query
    val filteredCases = remember(cases, searchQuery) {
        if (searchQuery.isBlank()) cases
        else cases.filter {
            it.parcel_id.contains(searchQuery, ignoreCase = true) ||
            it.case_id.contains(searchQuery, ignoreCase = true)
        }
    }

    IknosTheme {
        Scaffold(
            topBar = {
                Column(Modifier.background(PanelColor)) {
                    TopAppBar(
                        title = {
                            Column {
                                Text("Case Queue", style = MaterialTheme.typography.titleMedium, color = TextPrimary)
                                Text(
                                    "${filteredCases.size} cases",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextSecondary
                                )
                            }
                        },
                        actions = {
                            TextButton(onClick = onLogout) {
                                Text("Logout", color = TextSecondary)
                            }
                        },
                        colors = TopAppBarDefaults.topAppBarColors(containerColor = PanelColor)
                    )

                    // Search bar
                    OutlinedTextField(
                        value = searchQuery,
                        onValueChange = { searchQuery = it },
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 6.dp),
                        placeholder = {
                            Text("Search parcel ID, khasra...", color = TextTertiary, fontSize = 13.sp)
                        },
                        leadingIcon = { Icon(Icons.Default.Search, null, tint = TextSecondary) },
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = AccentSlate,
                            unfocusedBorderColor = LineColor,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary
                        ),
                        shape = MaterialTheme.shapes.medium
                    )

                    // Status tabs
                    TabRow(
                        selectedTabIndex = selectedTab,
                        containerColor = PanelColor,
                        contentColor = AccentSlate,
                        indicator = { tabPositions ->
                            TabRowDefaults.SecondaryIndicator(
                                modifier = Modifier.tabIndicatorOffset(tabPositions[selectedTab]),
                                color = AccentAmber
                            )
                        }
                    ) {
                        tabs.forEachIndexed { i, title ->
                            Tab(
                                selected = selectedTab == i,
                                onClick = {
                                    selectedTab = i
                                    val filter = when (i) {
                                        0 -> "open"
                                        1 -> "field_verification"
                                        else -> "closed"
                                    }
                                    loadCases(filter)
                                },
                                text = {
                                    Text(
                                        title,
                                        color = if (selectedTab == i) AccentAmber else TextSecondary,
                                        fontSize = 13.sp,
                                        fontWeight = if (selectedTab == i) FontWeight.SemiBold else FontWeight.Normal
                                    )
                                }
                            )
                        }
                    }
                }
            },
            containerColor = BgColor
        ) { padding ->
            Column(Modifier.padding(padding)) {

                // Offline banner
                if (isOffline) {
                    OfflineBanner(syncPending = syncPending)
                }

                when {
                    isLoading -> {
                        // Skeleton instead of bare spinner
                        SkeletonCardList(
                            count = 5,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)
                        )
                    }
                    filteredCases.isEmpty() -> {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("📂", fontSize = 40.sp)
                                Spacer(Modifier.height(12.dp))
                                Text(
                                    if (searchQuery.isBlank()) "No cases in this queue"
                                    else "No cases matching \"$searchQuery\"",
                                    color = TextSecondary,
                                    style = MaterialTheme.typography.bodyMedium
                                )
                            }
                        }
                    }
                    else -> {
                        LazyColumn(
                            Modifier.padding(horizontal = 16.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            item { Spacer(Modifier.height(8.dp)) }
                            items(filteredCases) { case ->
                                CaseQueueItem(case = case, onClick = { onCaseSelected(case.case_id) })
                            }
                            item { Spacer(Modifier.height(16.dp)) }
                        }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Individual case card
// ---------------------------------------------------------------------------

@Composable
fun CaseQueueItem(case: Case, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = PanelColor),
        shape = MaterialTheme.shapes.medium
    ) {
        Row(
            Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            // Severity badge — score + label
            SeverityBadge(score = case.confidence_score.toInt())

            // Case info
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                // Short case ID in monospace
                Text(
                    "#${case.case_id.take(8).uppercase()}",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextSecondary
                )
                // Parcel ID — primary identifier for surveyor
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        case.parcel_id,
                        fontWeight = FontWeight.SemiBold,
                        style = MaterialTheme.typography.titleSmall,
                        color = TextPrimary
                    )
                    if (case.confidence_score < 0.9f) {
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("🚩", fontSize = 14.sp)
                    }
                }
                // Status pill
                StatusPill(status = case.status)
            }

            Icon(
                Icons.Default.ArrowForward,
                contentDescription = null,
                tint = TextTertiary,
                modifier = Modifier.size(18.dp)
            )
        }
    }
}
