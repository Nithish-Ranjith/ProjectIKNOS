package com.example.projectiknos

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.projectiknos.api.RetrofitClient
import com.example.projectiknos.auth.AuthManager
import com.example.projectiknos.auth.LoginScreen
import com.example.projectiknos.customer.CustomerHomeScreen
import com.example.projectiknos.customer.FileObjectionScreen
import com.example.projectiknos.surveyor_field.CaseDetailScreen
import com.example.projectiknos.surveyor_field.CaseQueueScreen
import com.example.projectiknos.surveyor_field.DecisionScreen
import com.example.projectiknos.surveyor_field.FieldVerificationScreen
import com.example.projectiknos.surveyor_field.AOIPlanningScreen
import com.example.projectiknos.surveyor_field.FieldCommanderMissionScreen
import com.example.projectiknos.surveyor_field.PostFlightQCScreen
import com.example.projectiknos.surveyor_field.PreFlightScreen
import com.example.projectiknos.surveyor_drone.DroneCameraNodeScreen
import com.example.projectiknos.surveyor_drone.DroneParcelVerifyScreen
import com.example.projectiknos.surveyor_drone.MissionProcessScreen

class MainActivity : ComponentActivity() {
    private lateinit var authManager: AuthManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        authManager = AuthManager(this)

        // Restore token for existing session
        authManager.getToken()?.let {
            RetrofitClient.authToken = it
        }

        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    IKNOSApp(authManager)
                }
            }
        }
    }
}

@Composable
fun IKNOSApp(authManager: AuthManager) {
    val navController = rememberNavController()

    val initialRole = authManager.getRole()
    val startDest = when (initialRole) {
        "CUSTOMER" -> "customer_home"
        // Drone login → Step 1 (Parcel Verify), not the camera node directly
        "SURVEYOR_DRONE" -> "drone_parcel_verify/QUEUED"
        "SURVEYOR_FIELD", "SENIOR_FIELD" -> "field_home"
        else -> "login"
    }

    fun logout() {
        authManager.clear()
        RetrofitClient.authToken = null
        navController.navigate("login") { popUpTo(0) { inclusive = true } }
    }

    NavHost(navController = navController, startDestination = startDest) {

        // ---- Auth ----
        composable("login") {
            LoginScreen(
                authManager = authManager,
                onLoginSuccess = { role ->
                    val route = when (role) {
                        "CUSTOMER" -> "customer_home"
                        "SURVEYOR_DRONE" -> "drone_camera"  // Drone phone = camera node only
                        "SURVEYOR_FIELD", "SENIOR_FIELD" -> "field_home"
                        else -> "login"
                    }
                    navController.navigate(route) { popUpTo("login") { inclusive = true } }
                }
            )
        }

        // ---- Customer ----
        composable("customer_home") {
            CustomerHomeScreen(
                onFileObjection = { parcelId -> navController.navigate("file_objection/$parcelId") },
                onLogout = { logout() }
            )
        }
        composable(
            route = "file_objection/{parcel_id}",
            arguments = listOf(navArgument("parcel_id") { type = NavType.StringType })
        ) { back ->
            val parcelId = back.arguments?.getString("parcel_id") ?: ""
            FileObjectionScreen(parcelId = parcelId, onBack = { navController.popBackStack() })
        }

        // ---- Field Surveyor ----
        composable("field_home") {
            CaseQueueScreen(
                onCaseSelected = { caseId -> navController.navigate("case_detail/$caseId") },
                onLogout = { logout() }
            )
        }
        composable(
            route = "case_detail/{case_id}",
            arguments = listOf(navArgument("case_id") { type = NavType.StringType })
        ) { back ->
            val caseId = back.arguments?.getString("case_id") ?: ""
            CaseDetailScreen(
                caseId = caseId,
                onBack = { navController.popBackStack() },
                onNavigateToFieldVerification = { id -> navController.navigate("field_verification/$id") },
                onNavigateToDecision = { id -> navController.navigate("decision/$id") },
                onNavigateToPreFlight = { id -> navController.navigate("pre_flight/$id") }
            )
        }
        composable(
            route = "field_verification/{case_id}",
            arguments = listOf(navArgument("case_id") { type = NavType.StringType })
        ) { back ->
            val caseId = back.arguments?.getString("case_id") ?: ""
            FieldVerificationScreen(
                caseId = caseId,
                onBack = { navController.popBackStack() },
                onSubmitted = { navController.navigate("field_home") { popUpTo("field_home") } }
            )
        }
        composable(
            route = "decision/{case_id}",
            arguments = listOf(navArgument("case_id") { type = NavType.StringType })
        ) { back ->
            val caseId = back.arguments?.getString("case_id") ?: ""
            DecisionScreen(
                caseId = caseId,
                onBack = { navController.popBackStack() },
                onDecisionMade = { navController.navigate("field_home") { popUpTo("field_home") } }
            )
        }

        // ---- Field Surveyor: Mission Planning & Command Flow ----
        composable(
            route = "pre_flight/{case_id}",
            arguments = listOf(navArgument("case_id") { type = NavType.StringType })
        ) { back ->
            val caseId = back.arguments?.getString("case_id") ?: ""
            PreFlightScreen(
                onNavigateToAOI = { cId -> navController.navigate("aoi_planning/$cId") },
                onLogout = { logout() }
            )
        }
        composable(
            route = "aoi_planning/{case_id}",
            arguments = listOf(navArgument("case_id") { type = NavType.StringType })
        ) { back ->
            val caseId = back.arguments?.getString("case_id") ?: ""
            AOIPlanningScreen(
                caseId = caseId,
                onNavigateToMission = { cId, aoi ->
                    navController.navigate("live_mission/MISSION_TEMP")
                },
                onBack = { navController.popBackStack() }
            )
        }
        composable(
            route = "live_mission/{mission_id}",
            arguments = listOf(navArgument("mission_id") { type = NavType.StringType })
        ) { back ->
            val missionId = back.arguments?.getString("mission_id") ?: ""
            FieldCommanderMissionScreen(
                missionId = missionId,
                onMissionComplete = { id -> navController.navigate("post_flight_qc/$id") },
                onAbort = { navController.navigate("field_home") { popUpTo("field_home") } },
                onBack = { navController.popBackStack() }
            )
        }
        composable(
            route = "post_flight_qc/{mission_id}",
            arguments = listOf(navArgument("mission_id") { type = NavType.StringType })
        ) { back ->
            val missionId = back.arguments?.getString("mission_id") ?: ""
            PostFlightQCScreen(
                missionId = missionId,
                onPass = { navController.navigate("mission_process/$missionId") },
                onReflightRequired = { sector -> navController.navigate("live_mission/MISSION_TEMP") },
                onBack = { navController.popBackStack() }
            )
        }
        composable(
            route = "mission_process/{mission_id}",
            arguments = listOf(navArgument("mission_id") { type = NavType.StringType })
        ) { back ->
            val missionId = back.arguments?.getString("mission_id") ?: ""
            MissionProcessScreen(
                missionId = missionId,
                onDone = { navController.navigate("field_home") { popUpTo("field_home") } },
                onBack = { navController.navigate("post_flight_qc/$missionId") { popUpTo("post_flight_qc/$missionId") } }
            )
        }

        // ---- Drone Phone: CAMERA NODE ONLY ----
        // Drone login goes straight to camera capture node
        composable("drone_camera") {
            DroneCameraNodeScreen(
                missionId = "MISSION_TEMP",
                onMissionComplete = { logout() },
                onAbort = { logout() },
                onBack = { logout() }
            )
        }

        // ---- Drone Parcel Verify (Step 1) — accessed from Field via mission planning ----
        composable(
            route = "drone_parcel_verify/{case_id}",
            arguments = listOf(navArgument("case_id") { type = NavType.StringType })
        ) { back ->
            val caseId = back.arguments?.getString("case_id") ?: ""
            DroneParcelVerifyScreen(
                caseId = caseId,
                onApproved = { cId -> navController.navigate("aoi_planning/$cId") },
                onLogout = { logout() }
            )
        }
    }
}
