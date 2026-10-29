[app]
title = Chess By Lord
package.name = chessbylord
package.domain = ru.lord
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav,ttf,ogg,mp3
version = 1.4.2
android.numeric_version = 142

icon.filename = icon.png
presplash.filename = icon.png

# ЖЕСТКО ФИКСИРУЕМ ИДЕАЛЬНУЮ СВЯЗКУ
requirements = python3==3.11.5, kivy==2.3.0, cython==0.29.36

# Указываем актуальную ветку сборщика
p4a.branch = master

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET

# Оставляем NDK 25b
android.api = 31
android.minapi = 24
android.ndk = 25b
android.ndk_api = 21

android.gradle_parallel = False
android.gradle_daemon = False
