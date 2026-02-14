plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.protobuf)
}

android {
    namespace = "com.slabstech.health.elixir_t_echo"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.slabstech.health.elixir_t_echo"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            // Samsung A13 is 32-bit (armeabi-v7a).
            // MediaPipe 0.10.27+ supports both 32-bit and 64-bit.
            abiFilters.add("armeabi-v7a")
            abiFilters.add("arm64-v8a")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
    buildFeatures {
        compose = true
    }
    aaptOptions {
        noCompress("bin", "task", "tflite")
    }
    // Critical for loading large native libraries on older/budget devices
    packaging {
        jniLibs {
            useLegacyPackaging = true
            pickFirsts.add("lib/armeabi-v7a/libllm_inference_engine_jni.so")
            pickFirsts.add("lib/arm64-v8a/libllm_inference_engine_jni.so")
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)

    // USB Serial and Protobuf
    implementation(libs.usb.serial)
    implementation(libs.protobuf.javalite)

    // MediaPipe LLM Inference
    // MUST be 0.10.27 or higher for 32-bit (armeabi-v7a) support
    //implementation("com.google.mediapipe:tasks-genai:0.10.27")
    implementation("com.google.mediapipe:tasks-text:0.10.14")
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}

// Add protobuf configuration
protobuf {
    protoc {
        artifact = "com.google.protobuf:protoc:3.25.5"
    }
    generateProtoTasks {
        all().forEach { task ->
            task.builtins {
                create("java") {
                    option("lite")
                }
            }
        }
    }
}
