package com.example.projectiknos.surveyor_field

import android.app.Application
import android.content.Intent
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.projectiknos.surveyor_drone.CameraSchedulerService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class DroneCaptureMissionViewModel(application: Application) : AndroidViewModel(application) {

    private val _isMissionActive = MutableStateFlow(false)
    val isMissionActive: StateFlow<Boolean> = _isMissionActive.asStateFlow()

    fun startMission(missionId: String) {
        viewModelScope.launch {
            val context = getApplication<Application>().applicationContext
            val intent = Intent(context, CameraSchedulerService::class.java).apply {
                action = CameraSchedulerService.ACTION_START_MISSION
                putExtra(CameraSchedulerService.EXTRA_MISSION_ID, missionId)
            }
            context.startForegroundService(intent)
            _isMissionActive.value = true
        }
    }

    fun stopMission() {
        viewModelScope.launch {
            val context = getApplication<Application>().applicationContext
            val intent = Intent(context, CameraSchedulerService::class.java).apply {
                action = CameraSchedulerService.ACTION_STOP_MISSION
            }
            context.startService(intent) // stopService isn't needed, sending STOP action
            _isMissionActive.value = false
        }
    }
}
