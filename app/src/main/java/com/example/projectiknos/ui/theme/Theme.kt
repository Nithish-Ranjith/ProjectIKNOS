package com.example.projectiknos.ui.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// ---------------------------------------------------------------------------
// Surface Stack — warm dark grays, NOT pure black (avoids OLED halation)
// ---------------------------------------------------------------------------
val BgColor           = Color(0xFF0D1117)   // deepest background
val PanelColor        = Color(0xFF161B22)   // card surface
val PanelRaisedColor  = Color(0xFF1C2330)   // elevated modal / drawer
val LineColor         = Color(0xFF2D3748)   // dividers, borders (hairline)
val SurfaceOverlay    = Color(0xFF1A2332)   // hover / pressed state overlay

// ---------------------------------------------------------------------------
// Text — off-white hierarchy, never pure white
// ---------------------------------------------------------------------------
val TextPrimary   = Color(0xFFE2E8F0)   // main content — warm off-white
val TextSecondary = Color(0xFF8897AA)   // labels, metadata
val TextTertiary  = Color(0xFF556070)   // disabled, ultra-muted
// Backwards-compat aliases used in older screens
val TextColor   = TextPrimary
val MutedColor  = TextSecondary

// ---------------------------------------------------------------------------
// Semantic Accents — desaturated by ~30% from original neon values
// These tokens MUST be used in screens; raw hex is banned in screen files.
// ---------------------------------------------------------------------------
val AccentSlate      = Color(0xFF6B8CAE)   // primary action — calm steel blue
val AccentSlateLight = Color(0xFF8AAFD4)   // interactive hover / selected
val AccentSage       = Color(0xFF5A8A6A)   // success / clear / on-track
val AccentAmber      = Color(0xFFC49A3C)   // warning / under review / medium
val AccentRust       = Color(0xFFB85C4E)   // danger / high priority / flagged

// Backwards-compat aliases used in older components
val AccentBlue       = AccentSlate
val AccentGreen      = AccentSage
val AccentBlueDim    = Color(0x1A6B8CAE)   // 10% opacity
val AccentGreenDim   = Color(0x1A5A8A6A)   // 10% opacity
val DangerColor      = AccentRust

// ---------------------------------------------------------------------------
// Semantic status aliases — use these in screens, not the raw accent above
// ---------------------------------------------------------------------------
val ScoreHigh     = AccentRust    // score >= 75
val ScoreMedium   = AccentAmber   // score 50–74
val ScoreLow      = AccentSlate   // score < 50

val StatusClear     = AccentSage    // case status: closed / no issues
val StatusReview    = AccentAmber   // case status: field_verification / under review
val StatusConflict  = AccentRust    // case status: rejected / flagged
val StatusOpen      = AccentSlate   // case status: open

// ---------------------------------------------------------------------------
// Map-specific palette — forensic GIS aesthetic
// Used ONLY inside MapCanvas.kt; nowhere else
// ---------------------------------------------------------------------------
object MapColors {
    val DroneBoundary      = Color(0xFF00D4FF)   // cyan solid — drone-derived
    val CadastralBoundary  = Color(0xFFE05555)   // red dashed — cadastral record
    val DiscrepancyFill    = Color(0x40E05555)   // red at 25% — hatch zone fill
    val PhotoPoint         = Color(0xFFFFFFFF)   // white dot — capture point
    val DroneMarker        = Color(0xFF00D4FF)   // cyan dot — live drone position
    val FlightTrail        = Color(0xFF00D4FF)   // cyan trail
    val GridLine           = Color(0x5588AACC)   // dim blue-gray grid
    val CanvasBackground   = Color(0xFF1A2332)   // fallback when no tile
    val LedgerBar          = Color(0xCC0D1117)   // 80% opaque dark for footer bar
    val InfoPanel          = Color(0xE6161B22)   // 90% opaque dark for panel
    val InfoPanelBorder    = Color(0xFF2D3748)
    val FlaggedText        = Color(0xFFE05555)
    val ClearText          = Color(0xFF5A8A6A)
}

// ---------------------------------------------------------------------------
// Material 3 Color Scheme
// ---------------------------------------------------------------------------
private val IknosDarkColorScheme = darkColorScheme(
    background       = BgColor,
    surface          = PanelColor,
    surfaceVariant   = PanelRaisedColor,
    onBackground     = TextPrimary,
    onSurface        = TextPrimary,
    onSurfaceVariant = TextSecondary,
    primary          = AccentSlate,
    onPrimary        = Color.White,
    secondary        = AccentSage,
    onSecondary      = Color.White,
    tertiary         = AccentAmber,
    error            = AccentRust,
    onError          = Color.White,
    outline          = LineColor,
    outlineVariant   = SurfaceOverlay
)

// ---------------------------------------------------------------------------
// Typography
// ---------------------------------------------------------------------------
val IknosTypography = Typography(
    bodyLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 22.4.sp,       // 1.6× for readability
        letterSpacing = 0.01.sp,
        color = TextPrimary
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 13.sp,
        lineHeight = 20.8.sp,
        color = TextPrimary
    ),
    bodySmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        lineHeight = 18.sp,
        color = TextSecondary
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 18.sp,
        lineHeight = 26.sp,
        color = TextPrimary
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 15.sp,
        lineHeight = 22.sp,
        color = TextPrimary
    ),
    titleSmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 13.sp,
        lineHeight = 20.sp,
        color = TextPrimary
    ),
    labelLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,     // min Medium — never Light on dark
        fontSize = 13.sp,
        lineHeight = 18.sp,
        letterSpacing = 0.03.sp,
        color = TextPrimary
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.04.sp,
        color = TextSecondary
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.Monospace,  // monospace for codes, IDs, coordinates
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.02.sp,
        color = TextSecondary
    )
)

// Monospace style used in forensic map panels and audit logs
val MonoStyle = TextStyle(
    fontFamily = FontFamily.Monospace,
    fontWeight = FontWeight.Normal,
    fontSize = 11.sp,
    lineHeight = 17.sp,
    letterSpacing = 0.sp,
    color = TextPrimary
)

val MonoSmall = TextStyle(
    fontFamily = FontFamily.Monospace,
    fontWeight = FontWeight.Normal,
    fontSize = 10.sp,
    lineHeight = 15.sp,
    color = TextSecondary
)

// ---------------------------------------------------------------------------
// Theme wrapper
// ---------------------------------------------------------------------------
@Composable
fun IknosTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = IknosDarkColorScheme,
        typography = IknosTypography,
        content = content
    )
}
