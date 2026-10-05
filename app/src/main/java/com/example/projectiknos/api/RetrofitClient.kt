package com.example.projectiknos.api

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import okhttp3.Interceptor
import java.util.concurrent.TimeUnit

object RetrofitClient {
    // Default IP — updated to current LAN IP.
    // Change this to match your Mac's IP if you switch networks.
    // Use 10.0.2.2 for the Android Emulator (maps to host machine's localhost).
    private var _baseUrl: String = "http://172.20.10.4:8000/"

    var baseUrl: String
        get() = _baseUrl
        set(value) {
            var url = value.trim()
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                url = "http://$url"
            }
            if (!url.endsWith("/")) {
                url = "$url/"
            }
            _baseUrl = url
            _instance = null  // Force rebuild of Retrofit instance with new URL
        }

    // Auth token — set after successful login
    var authToken: String? = null

    private val authInterceptor = Interceptor { chain ->
        val original = chain.request()
        val requestBuilder = original.newBuilder()
        authToken?.let {
            requestBuilder.header("Authorization", "Bearer $it")
        }
        chain.proceed(requestBuilder.build())
    }

    private val logging = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    // Rebuild OkHttp client each time so timeouts are consistent
    private fun buildClient(): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(logging)
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .build()

    @Volatile
    private var _instance: IKNOSApi? = null

    val instance: IKNOSApi
        get() {
            return _instance ?: synchronized(this) {
                _instance ?: run {
                    val retrofit = Retrofit.Builder()
                        .baseUrl(_baseUrl)
                        .client(buildClient())
                        .addConverterFactory(GsonConverterFactory.create())
                        .build()
                    val api = retrofit.create(IKNOSApi::class.java)
                    _instance = api
                    api
                }
            }
        }
}
