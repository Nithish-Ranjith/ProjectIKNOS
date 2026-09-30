package com.example.projectiknos.ui.components

import android.content.Context
import android.view.MotionEvent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.example.projectiknos.surveyor_drone.GridBlock
import com.example.projectiknos.ui.theme.*
import org.osmdroid.config.Configuration
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Polygon
import org.osmdroid.views.overlay.Polyline
import androidx.compose.foundation.Canvas as ComposeCanvas

// ---------------------------------------------------------------------------
// Spatial discrepancy data passed into the map from the backend response
// ---------------------------------------------------------------------------
data class DiscrepancyMetrics(
    val hausdorffM: Double,          // dH value from spatial_service.py
    val hausdorffLat: Double,        // approximate lat of max intrusion point
    val areaDiffPct: Double,         // ΔArea %
    val titleAreaAc: Double,         // cadastral area in acres
    val observedAreaAc: Double,      // drone-derived area in acres
    val scaledIoU: Double,           // IoU (Intersection over Union)
    val iouThreshold: Double = 0.890,// acceptance threshold from config
    val statusLabel: String,         // "FLAGGED" | "CLEAR" | "PENDING"
    val escalationNote: String,      // "ESCALATE TO SENIOR TAHSILDAR (LEVEL-2)"
    val sha256: String = "",         // audit chain hash from audit_service.py
    val officerCode: String = "",    // authenticated officer ID
    val mutationNote: String = ""    // e.g. "v2 MUTATION PENDING SIGNATURE"
)

// ---------------------------------------------------------------------------
// TacticalMap — forensic GIS map matching the reference screenshot.
// Renders using OSMDroid satellite tiles with Compose Canvas overlay.
// ---------------------------------------------------------------------------
@Composable
fun TacticalMap(
    modifier: Modifier = Modifier,
    cadastralPoly: List<Pair<Double, Double>>?,
    adjustedPoly: List<Pair<Double, Double>>?,
    blocks: List<GridBlock>?,
    dronePos: Pair<Double, Double>?,
    flightTrail: List<Pair<Double, Double>>?,
    discrepancy: DiscrepancyMetrics? = null,
    // Layer toggles — driven by FAB toolbar
    showCadastral: Boolean = true,
    showAdjusted: Boolean = true,
    showGrid: Boolean = false,
    showPoints: Boolean = true,
    showBlocks: Boolean = true,
    showTrail: Boolean = true,
    // Whether to use OSMDroid tile base (set true when real geo coords available)
    useTileBase: Boolean = false,
    // Real-world geo center for tile view (required if useTileBase = true)
    centerGeoPoint: GeoPoint? = null
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .clip(RoundedCornerShape(8.dp))
    ) {

        // ── Base layer: OSMDroid satellite tiles or procedural dark canvas ──
        if (useTileBase && centerGeoPoint != null) {
            OsmSatelliteBase(
                modifier = Modifier.fillMaxSize(),
                center = centerGeoPoint,
                zoomLevel = 17.0
            )
        } else {
            // Procedural terrain-color background (matches the brown/green field look)
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color(0xFF2C3A28))  // base olive-brown like dry field
            )
        }

        // ── Geometry overlay using Compose Canvas ──
        ComposeCanvas(modifier = Modifier.fillMaxSize()) {
            val bb = computeBoundingBox(cadastralPoly, adjustedPoly)
                ?: return@ComposeCanvas

            val w = bb[1] - bb[0]; val h = bb[3] - bb[2]
            val padW = w * 0.14; val padH = h * 0.14
            val minX = bb[0] - padW; val maxX = bb[1] + padW
            val minY = bb[2] - padH; val maxY = bb[3] + padH
            val rangeX = maxX - minX; val rangeY = maxY - minY
            val scale = minOf(size.width / rangeX, size.height / rangeY).toFloat()
            val offsetX = (size.width - rangeX * scale) / 2f
            val offsetY = (size.height - rangeY * scale) / 2f

            fun toScreen(pt: Pair<Double, Double>): Offset {
                val sx = ((pt.first - minX) * scale + offsetX).toFloat()
                val sy = ((pt.second - minY) * scale + offsetY).toFloat()
                return Offset(sx, sy)
            }

            // 1. Draw muted procedural field lines for texture (if no tiles)
            if (!useTileBase) {
                drawFieldLines(size)
            }

            // 2. Discrepancy hatch zone between the two polygons
            if (showCadastral && showAdjusted &&
                cadastralPoly != null && adjustedPoly != null &&
                cadastralPoly.isNotEmpty() && adjustedPoly.isNotEmpty()
            ) {
                drawDiscrepancyHatch(
                    cadastralPoly.map { toScreen(it) },
                    adjustedPoly.map { toScreen(it) },
                    size
                )
            }

            // 3. Cadastral boundary — RED DASHED (government record)
            if (showCadastral && cadastralPoly != null && cadastralPoly.isNotEmpty()) {
                val path = buildPath(cadastralPoly.map { toScreen(it) }, close = true)
                // Fill — very faint red
                drawPath(path, color = MapColors.CadastralBoundary.copy(alpha = 0.08f))
                // Dashed red stroke
                drawPath(
                    path = path,
                    color = MapColors.CadastralBoundary,
                    style = Stroke(
                        width = 4f,
                        pathEffect = PathEffect.dashPathEffect(floatArrayOf(18f, 10f), 0f)
                    )
                )
            }

            // 4. Drone-derived boundary — CYAN SOLID
            if (showAdjusted && adjustedPoly != null && adjustedPoly.isNotEmpty()) {
                val path = buildPath(adjustedPoly.map { toScreen(it) }, close = true)
                // Fill — very faint cyan
                drawPath(path, color = MapColors.DroneBoundary.copy(alpha = 0.08f))
                // Solid cyan stroke
                drawPath(
                    path = path,
                    color = MapColors.DroneBoundary,
                    style = Stroke(width = 5f)
                )
            }

            // 5. Grid blocks (lawnmower rows)
            if (showBlocks && blocks != null) {
                blocks.forEach { b ->
                    val p1 = toScreen(b.x0 to b.y0)
                    val p2 = toScreen((b.x0 + b.w) to (b.y0 + b.h))
                    drawRect(
                        color = MapColors.GridLine,
                        topLeft = p1,
                        size = Size(p2.x - p1.x, p2.y - p1.y),
                        style = Stroke(
                            width = 1.5f,
                            pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 8f))
                        )
                    )
                }
            }

            // 6. Flight path grid lines
            if (showGrid && blocks != null) {
                blocks.forEach { b ->
                    b.lines.forEach { line ->
                        drawLine(
                            color = MapColors.GridLine,
                            start = toScreen(line.x to line.y0),
                            end = toScreen(line.x to line.y1),
                            strokeWidth = 2f,
                            pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 8f))
                        )
                    }
                }
            }

            // 7. Photo capture points (white dots)
            if (showPoints && blocks != null) {
                blocks.forEach { b ->
                    b.photoPoints.forEach { pt ->
                        val center = toScreen(pt.x to pt.y)
                        drawCircle(
                            color = MapColors.PhotoPoint.copy(alpha = 0.9f),
                            radius = 5f,
                            center = center
                        )
                    }
                }
            }

            // 8. Flight trail — cyan line showing path taken
            if (showTrail && flightTrail != null && flightTrail.size >= 2) {
                val path = buildPath(flightTrail.map { toScreen(it) }, close = false)
                drawPath(
                    path = path,
                    color = MapColors.FlightTrail,
                    style = Stroke(width = 4f)
                )
            }

            // 9. Live drone position — cyan pulsing circle
            if (dronePos != null) {
                val pt = toScreen(dronePos)
                // Outer ring
                drawCircle(
                    color = MapColors.DroneMarker.copy(alpha = 0.25f),
                    radius = 28f,
                    center = pt
                )
                // Middle ring
                drawCircle(
                    color = MapColors.DroneMarker.copy(alpha = 0.5f),
                    radius = 18f,
                    center = pt,
                    style = Stroke(width = 2.5f)
                )
                // Inner fill
                drawCircle(
                    color = MapColors.DroneMarker,
                    radius = 8f,
                    center = pt
                )
                drawCircle(
                    color = Color.Black,
                    radius = 8f,
                    center = pt,
                    style = Stroke(width = 2.5f)
                )
            }
        }

        // ── Left toolbar ──
        MapToolbarLeft(modifier = Modifier.align(Alignment.CenterStart).padding(start = 8.dp))

        // ── Right toolbar ──
        MapToolbarRight(modifier = Modifier.align(Alignment.CenterEnd).padding(end = 8.dp))

        // ── Legend chip — top left ──
        MapLegend(modifier = Modifier.align(Alignment.TopStart).padding(8.dp))

        // ── Forensic info panel — bottom right (when discrepancy available) ──
        if (discrepancy != null) {
            ForensicInfoPanel(
                metrics = discrepancy,
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(end = 12.dp, bottom = 44.dp)
                    .widthIn(max = 340.dp)
            )
        }

        // ── Tamper-proof ledger footer ──
        if (discrepancy != null && discrepancy.sha256.isNotBlank()) {
            LedgerFooter(
                sha256 = discrepancy.sha256,
                officerCode = discrepancy.officerCode,
                mutationNote = discrepancy.mutationNote,
                modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth()
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Sub-composables
// ---------------------------------------------------------------------------

@Composable
private fun MapToolbarLeft(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .background(MapColors.InfoPanel, RoundedCornerShape(6.dp))
            .border(1.dp, MapColors.InfoPanelBorder, RoundedCornerShape(6.dp))
            .padding(vertical = 6.dp, horizontal = 4.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        val tools = listOf("⊕", "🔍", "🗺", "✏", "⊞", "≡")
        tools.forEach { icon ->
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .clickable { /* Layer/zoom/draw actions */ },
                contentAlignment = Alignment.Center
            ) {
                Text(icon, fontSize = 16.sp, color = TextSecondary)
            }
        }
    }
}

@Composable
private fun MapToolbarRight(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .background(MapColors.InfoPanel, RoundedCornerShape(6.dp))
            .border(1.dp, MapColors.InfoPanelBorder, RoundedCornerShape(6.dp))
            .padding(vertical = 6.dp, horizontal = 4.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        val tools = listOf("⊞", "+", "−", "⤡", "⚙")
        tools.forEach { icon ->
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .clickable { /* Zoom/settings actions */ },
                contentAlignment = Alignment.Center
            ) {
                Text(icon, fontSize = 16.sp, color = TextSecondary)
            }
        }
    }
}

@Composable
private fun MapLegend(modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .background(MapColors.InfoPanel, RoundedCornerShape(6.dp))
            .border(1.dp, MapColors.InfoPanelBorder, RoundedCornerShape(6.dp))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Cadastral — red dashed
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            Text("╌╌", color = MapColors.CadastralBoundary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            Text("Cadastral", style = MonoSmall)
        }
        // Drone — cyan solid
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            Text("──", color = MapColors.DroneBoundary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            Text("Drone-derived", style = MonoSmall)
        }
        // Mismatch — red fill swatch
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .background(MapColors.CadastralBoundary.copy(alpha = 0.45f), RoundedCornerShape(2.dp))
            )
            Text("Mismatch", style = MonoSmall)
        }
    }
}

@Composable
private fun ForensicInfoPanel(metrics: DiscrepancyMetrics, modifier: Modifier = Modifier) {
    val statusColor = when (metrics.statusLabel.uppercase()) {
        "FLAGGED" -> MapColors.FlaggedText
        "CLEAR"   -> MapColors.ClearText
        else      -> TextSecondary
    }

    Column(
        modifier = modifier
            .background(MapColors.InfoPanel, RoundedCornerShape(8.dp))
            .border(1.dp, MapColors.InfoPanelBorder, RoundedCornerShape(8.dp))
            .padding(14.dp)
    ) {
        // Header
        Text(
            "SURVEY PARCEL AUDIT // STATUTORY FORENSICS",
            style = MonoSmall.copy(color = TextSecondary, fontWeight = FontWeight.Bold),
            letterSpacing = 0.5.sp
        )
        Spacer(Modifier.height(10.dp))

        // Metrics
        ForensicRow(
            "dH (Hausdorff Intrusion):",
            "%.3f m @ N %.4f°".format(metrics.hausdorffM, metrics.hausdorffLat)
        )
        ForensicRow(
            "Discrepancy (ΔArea):",
            "+%.2f%% (Title: %.2f Ac vs Obs: %.2f Ac)".format(
                metrics.areaDiffPct, metrics.titleAreaAc, metrics.observedAreaAc
            )
        )
        ForensicRow(
            "Scaled IoU:",
            "%.3f (Acceptance Threshold: %.3f)".format(metrics.scaledIoU, metrics.iouThreshold)
        )

        Spacer(Modifier.height(10.dp))

        // Status line
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("STATUS:", style = MonoSmall.copy(color = TextSecondary))
            Text(
                metrics.statusLabel.uppercase(),
                style = MonoSmall.copy(color = statusColor, fontWeight = FontWeight.Bold),
                fontSize = 11.sp
            )
            if (metrics.escalationNote.isNotBlank()) {
                Text("// ${metrics.escalationNote}", style = MonoSmall)
            }
        }
    }
}

@Composable
private fun ForensicRow(label: String, value: String) {
    Column(modifier = Modifier.padding(vertical = 2.dp)) {
        Text(label, style = MonoSmall.copy(color = TextSecondary))
        Text(value, style = MonoStyle.copy(fontSize = 11.5.sp))
    }
}

@Composable
private fun LedgerFooter(
    sha256: String,
    officerCode: String,
    mutationNote: String,
    modifier: Modifier = Modifier
) {
    val shortHash = if (sha256.length > 16) "${sha256.take(8)}...${sha256.takeLast(4)}" else sha256
    val footerText = buildString {
        append("[TAMPER-PROOF LEDGER] SHA-256: $shortHash")
        if (officerCode.isNotBlank()) append(" // AUTHENTICATED: $officerCode")
        if (mutationNote.isNotBlank()) append(" // $mutationNote")
    }

    Box(
        modifier = modifier
            .background(MapColors.LedgerBar)
            .padding(horizontal = 12.dp, vertical = 4.dp)
    ) {
        Text(footerText, style = MonoSmall.copy(color = TextTertiary), maxLines = 1)
    }
}

// ---------------------------------------------------------------------------
// OSMDroid satellite tile base (used when real geo coords are available)
// ---------------------------------------------------------------------------
@Composable
private fun OsmSatelliteBase(
    modifier: Modifier = Modifier,
    center: GeoPoint,
    zoomLevel: Double
) {
    val context = LocalContext.current
    AndroidView(
        modifier = modifier,
        factory = { ctx ->
            Configuration.getInstance().userAgentValue = ctx.packageName
            MapView(ctx).apply {
                setTileSource(TileSourceFactory.MAPNIK)  // swap to satellite tile source if key available
                setMultiTouchControls(false)
                isClickable = false
                controller.setZoom(zoomLevel)
                controller.setCenter(center)
                isTilesScaledToDpi = true
            }
        },
        update = { mapView ->
            mapView.controller.setCenter(center)
            mapView.controller.setZoom(zoomLevel)
        }
    )
}

// ---------------------------------------------------------------------------
// Canvas draw helpers
// ---------------------------------------------------------------------------

private fun DrawScope.drawFieldLines(canvasSize: Size) {
    // Subtle horizontal terrain lines to mimic aerial field texture
    val lineColor = Color(0xFF3A4A35).copy(alpha = 0.6f)
    val spacing = canvasSize.height / 18f
    var y = 0f
    while (y < canvasSize.height) {
        drawLine(
            color = lineColor,
            start = Offset(0f, y),
            end = Offset(canvasSize.width, y),
            strokeWidth = 1f
        )
        y += spacing
    }
}

private fun DrawScope.drawDiscrepancyHatch(
    poly1: List<Offset>,
    poly2: List<Offset>,
    canvasSize: Size
) {
    if (poly1.isEmpty() || poly2.isEmpty()) return
    // Diagonal hatch lines clipped to approximate bounding box of mismatch zone
    // In a real impl, this would use the ST_Difference polygon — for demo, we
    // draw hatching over both polygons' combined bbox with the discrepancy fill color.
    val allPts = poly1 + poly2
    val minX = allPts.minOf { it.x }
    val maxX = allPts.maxOf { it.x }
    val minY = allPts.minOf { it.y }
    val maxY = allPts.maxOf { it.y }

    val spacing = 14f
    var startX = minX - (maxY - minY)
    while (startX < maxX + (maxY - minY)) {
        drawLine(
            color = MapColors.CadastralBoundary.copy(alpha = 0.35f),
            start = Offset(startX, minY),
            end = Offset(startX + (maxY - minY), maxY),
            strokeWidth = 2f
        )
        startX += spacing
    }
}

private fun buildPath(points: List<Offset>, close: Boolean): Path {
    return Path().apply {
        if (points.isEmpty()) return@apply
        moveTo(points.first().x, points.first().y)
        for (i in 1 until points.size) {
            lineTo(points[i].x, points[i].y)
        }
        if (close) close()
    }
}

private fun computeBoundingBox(
    p1: List<Pair<Double, Double>>?,
    p2: List<Pair<Double, Double>>?
): DoubleArray? {
    val allPts = (p1 ?: emptyList()) + (p2 ?: emptyList())
    if (allPts.isEmpty()) return null
    val xs = allPts.map { it.first }
    val ys = allPts.map { it.second }
    return doubleArrayOf(
        xs.minOrNull() ?: 0.0, xs.maxOrNull() ?: 0.0,
        ys.minOrNull() ?: 0.0, ys.maxOrNull() ?: 0.0
    )
}
