import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val buildWebAssets by tasks.registering(Exec::class) {
    workingDir(rootProject.file("../frontend"))
    commandLine("pnpm", "build:android")
}

val syncWebAssets by tasks.registering(Copy::class) {
    dependsOn(buildWebAssets)
    outputs.upToDateWhen { false }
    doFirst {
        layout.projectDirectory.dir("src/main/assets/web").asFile.deleteRecursively()
    }
    from(rootProject.file("../frontend/dist"))
    into(layout.projectDirectory.dir("src/main/assets/web"))
}

val signingProperties = Properties().apply {
    val file = rootProject.file("../.secrets/keystore.properties")
    if (file.isFile) file.inputStream().use(::load)
}
val releaseStorePath =
    System.getenv("ANDROID_KEYSTORE_PATH") ?: signingProperties.getProperty("storeFile")
val releaseStorePassword =
    System.getenv("ANDROID_KEYSTORE_PASSWORD") ?: signingProperties.getProperty("storePassword")
val releaseKeyAlias =
    System.getenv("ANDROID_KEY_ALIAS") ?: signingProperties.getProperty("keyAlias")
val releaseKeyPassword =
    System.getenv("ANDROID_KEY_PASSWORD") ?: signingProperties.getProperty("keyPassword")
val hasReleaseSigning = listOf(
    releaseStorePath,
    releaseStorePassword,
    releaseKeyAlias,
    releaseKeyPassword
).all { !it.isNullOrBlank() }

android {
    namespace = "ai.panvv.crazygame"
    compileSdk = 36

    defaultConfig {
        applicationId = "ai.panvv.crazygame"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources.excludes += setOf("META-INF/AL2.0", "META-INF/LGPL2.1")
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = rootProject.file(releaseStorePath!!)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            if (hasReleaseSigning) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

tasks.named("preBuild") {
    dependsOn(syncWebAssets)
}

dependencies {
    implementation("androidx.work:work-runtime-ktx:2.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
