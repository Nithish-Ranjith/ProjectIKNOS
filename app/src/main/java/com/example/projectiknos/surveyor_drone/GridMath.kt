package com.example.projectiknos.surveyor_drone

import kotlin.math.*

data class Coordinate(val lat: Double, val lon: Double)
data class GridConfig(val cols: Int, val rows: Int)
data class CameraConfig(val fovDeg: Double, val altitudeM: Double, val forwardOverlap: Double, val sideOverlap: Double)

data class FlightLine(val x: Double, val y0: Double, val y1: Double, val reverse: Boolean)
data class PhotoPoint(val x: Double, val y: Double)
data class GridBlock(
    val id: String,
    val x0: Double, val y0: Double, val w: Double, val h: Double,
    val cx: Double, val cy: Double,
    val lines: List<FlightLine>,
    val photoPoints: List<PhotoPoint>
)

data class GridMathResult(
    val blocks: List<GridBlock>,
    val lineSpacingM: Double,
    val photoSpacingM: Double,
    val metersPerSvgUnit: Double
)

object GridMath {

    // Helper: area of a simple polygon
    fun polygonArea(poly: List<Pair<Double, Double>>): Double {
        var a = 0.0
        for (i in poly.indices) {
            val p1 = poly[i]
            val p2 = poly[(i + 1) % poly.size]
            a += p1.first * p2.second - p2.first * p1.second
        }
        return abs(a) / 2.0
    }

    // Helper: bounding box
    fun bbox(poly: List<Pair<Double, Double>>): DoubleArray {
        val xs = poly.map { it.first }
        val ys = poly.map { it.second }
        return doubleArrayOf(xs.minOrNull() ?: 0.0, xs.maxOrNull() ?: 0.0, ys.minOrNull() ?: 0.0, ys.maxOrNull() ?: 0.0)
    }

    // Helper: point in polygon
    fun pointInPoly(pt: Pair<Double, Double>, poly: List<Pair<Double, Double>>): Boolean {
        var inside = false
        var j = poly.size - 1
        for (i in poly.indices) {
            val xi = poly[i].first
            val yi = poly[i].second
            val xj = poly[j].first
            val yj = poly[j].second

            val intersect = ((yi > pt.second) != (yj > pt.second))
                    && (pt.first < (xj - xi) * (pt.second - yi) / (yj - yi) + xi)
            if (intersect) inside = !inside
            j = i
        }
        return inside
    }

    private fun computeCameraFootprint(cam: CameraConfig): Pair<Double, Double> {
        val halfFovRad = Math.toRadians(cam.fovDeg / 2.0)
        val footprintWidthM = 2.0 * cam.altitudeM * tan(halfFovRad)
        val footprintHeightM = footprintWidthM * 0.75 // 4:3 aspect ratio
        return Pair(footprintWidthM, footprintHeightM)
    }

    /**
     * Compute grid blocks and flight lines.
     * @param poly The boundary polygon in an arbitrary local coordinate space (e.g. SVG units)
     * @param claimedAreaHa The real-world claimed area in hectares to establish the scale factor
     */
    fun computeGrid(poly: List<Pair<Double, Double>>, claimedAreaHa: Double, gridCfg: GridConfig, cam: CameraConfig): GridMathResult {
        // Find scale factor (meters per SVG unit)
        val polyAreaUnits = polygonArea(poly)
        val claimedAreaM2 = claimedAreaHa * 10000.0
        val metersPerUnit = sqrt(claimedAreaM2 / polyAreaUnits)

        val bb = bbox(poly)
        val minX = bb[0]; val maxX = bb[1]; val minY = bb[2]; val maxY = bb[3]
        val w = maxX - minX
        val h = maxY - minY
        val blockW = w / gridCfg.cols
        val blockH = h / gridCfg.rows

        val (footprintWidthM, footprintHeightM) = computeCameraFootprint(cam)
        val lineSpacingM = footprintWidthM * (1.0 - cam.sideOverlap)
        val photoSpacingM = footprintHeightM * (1.0 - cam.forwardOverlap)

        val blocks = mutableListOf<GridBlock>()
        var idx = 1

        for (r in 0 until gridCfg.rows) {
            for (c in 0 until gridCfg.cols) {
                val x0 = minX + c * blockW
                val y0 = minY + r * blockH
                val cx = x0 + blockW / 2.0
                val cy = y0 + blockH / 2.0

                // Keep block if its center is in poly, or any of its corners
                if (!pointInPoly(cx to cy, poly)) {
                    val corners = listOf(x0 to y0, (x0+blockW) to y0, x0 to (y0+blockH), (x0+blockW) to (y0+blockH))
                    if (corners.none { pointInPoly(it, poly) }) continue
                }

                // Compute flight lines
                val nLines = max(1, Math.round((blockW * metersPerUnit) / lineSpacingM).toInt())
                val lines = mutableListOf<FlightLine>()
                for (l in 0..nLines) {
                    val lx = x0 + (blockW * l.toDouble() / nLines)
                    lines.add(FlightLine(lx, y0, y0 + blockH, l % 2 == 1))
                }

                // Compute photo points
                val photoPoints = mutableListOf<PhotoPoint>()
                for (line in lines) {
                    val nPts = max(2, Math.round((blockH * metersPerUnit) / photoSpacingM).toInt())
                    for (p in 0..nPts) {
                        val py = line.y0 + (blockH * p.toDouble() / nPts)
                        photoPoints.add(PhotoPoint(line.x, py))
                    }
                }

                blocks.add(
                    GridBlock(
                        id = "B$idx",
                        x0 = x0, y0 = y0, w = blockW, h = blockH, cx = cx, cy = cy,
                        lines = lines, photoPoints = photoPoints
                    )
                )
                idx++
            }
        }

        return GridMathResult(blocks, lineSpacingM, photoSpacingM, metersPerUnit)
    }
}
