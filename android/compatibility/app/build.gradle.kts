plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

android {
    namespace = "ai.panvv.crazygame.probe"
    compileSdk = 36

    defaultConfig {
        applicationId = "ai.panvv.crazygame.probe"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        buildPython("../../../.venv/bin/python")
        pip {
            install("fastapi==0.162.2")
            install("pydantic==2.14.3")
            install("pydantic-settings==2.16.2")
            install("cryptography==42.0.8")
            install("sqlalchemy==2.1.8")
            install("apscheduler==3.11.3")
            install("httpx==0.28.1")
            install("python-multipart==0.0.33")
            install("uvicorn==0.54.0")
            install("tzdata")
        }
    }
}
