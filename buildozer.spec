[app]
title = Chess
package.name = mychess
package.domain = org.test

# Путь к исходникам
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav

# Версия
version = 1.0

# Зависимости (добавлен Cython, он нужен для Kivy)
requirements = python3,kivy==2.3.0,cython

# Настройки экрана
orientation = portrait
fullscreen = 0

# Настройки Android
android.archs = arm64-v8a
android.accept_sdk_license = True

# Явно задаем версии API и NDK, чтобы Buildozer не скачивал несовместимые
android.api = 33
android.minapi = 24
android.ndk = 25b
