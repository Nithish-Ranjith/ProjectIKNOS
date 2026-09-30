package com.example.projectiknos

import com.example.projectiknos.surveyor_drone.CameraConfig
import com.example.projectiknos.surveyor_drone.GridConfig
import com.example.projectiknos.surveyor_drone.GridMath
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

class GridMathTest {

    @Test
    fun testPolygonArea() {
        // Simple 10x10 square
        val square = listOf(
            0.0 to 0.0,
            10.0 to 0.0,
            10.0 to 10.0,
            0.0 to 10.0
        )
        val area = GridMath.polygonArea(square)
        assertEquals(100.0, area, 0.001)
    }

    @Test
    fun testBBox() {
        val poly = listOf(
            2.0 to 1.0,
            8.0 to 3.0,
            5.0 to 9.0
        )
        val bbox = GridMath.bbox(poly)
        // expected: minX=2, maxX=8, minY=1, maxY=9
        assertEquals(2.0, bbox[0], 0.001)
        assertEquals(8.0, bbox[1], 0.001)
        assertEquals(1.0, bbox[2], 0.001)
        assertEquals(9.0, bbox[3], 0.001)
    }

    @Test
    fun testPointInPoly() {
        val square = listOf(
            0.0 to 0.0,
            10.0 to 0.0,
            10.0 to 10.0,
            0.0 to 10.0
        )
        assertTrue("Point should be inside", GridMath.pointInPoly(5.0 to 5.0, square))
        assertTrue("Point should be outside", !GridMath.pointInPoly(15.0 to 5.0, square))
    }

    @Test
    fun testComputeGrid() {
        val square = listOf(
            0.0 to 0.0,
            100.0 to 0.0,
            100.0 to 100.0,
            0.0 to 100.0
        )
        val camCfg = CameraConfig(fovDeg = 60.0, altitudeM = 50.0, forwardOverlap = 0.7, sideOverlap = 0.6)
        val gridCfg = GridConfig(cols = 2, rows = 2)

        val result = GridMath.computeGrid(square, 1.0, gridCfg, camCfg)
        
        // With 2x2 grid, there should be exactly 4 blocks for a perfect square
        assertEquals(4, result.blocks.size)
        
        // Verify scale factor mapping 1 hectare (10000 m2) to 10000 SVG units squared
        assertEquals(1.0, result.metersPerSvgUnit, 0.01)
        
        // Verify block 1 details
        val b1 = result.blocks[0]
        assertEquals("B1", b1.id)
        assertEquals(0.0, b1.x0, 0.01)
        assertEquals(0.0, b1.y0, 0.01)
        assertEquals(50.0, b1.w, 0.01)
        assertEquals(50.0, b1.h, 0.01)
        
        // Should have photo points generated
        assertTrue(b1.photoPoints.isNotEmpty())
    }
}
