[app]
title = Chess
package.name = mychess
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav
version = 1.0

# Ключевое исправление: принудительно указываем старый Cython
requirements = python3,kivy==2.3.0,cython<3.0

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.accept_sdk_license = True
android.api = 33
android.minapi = 24
android.ndk = 25b
