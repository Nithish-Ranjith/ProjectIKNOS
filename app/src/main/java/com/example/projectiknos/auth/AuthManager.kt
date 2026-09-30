package com.example.projectiknos.auth

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class AuthManager(context: Context) {

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val sharedPreferences = EncryptedSharedPreferences.create(
        context,
        "terratrace_auth_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun saveToken(token: String, role: String) {
        sharedPreferences.edit()
            .putString("auth_token", token)
            .putString("user_role", role)
            .apply()
    }

    fun getToken(): String? = sharedPreferences.getString("auth_token", null)
    fun getRole(): String? = sharedPreferences.getString("user_role", null)

    fun clear() {
        sharedPreferences.edit().clear().apply()
    }
}
