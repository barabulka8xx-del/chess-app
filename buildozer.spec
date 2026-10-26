[app]
title = Chess
package.name = mychess
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav,ttf
version = 1.0

# Версии зафиксированы для стабильной сборки
requirements = python3==3.10.13, hostpython3==3.10.13, kivy==2.3.0, cython==0.29.33

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.accept_sdk_license = True
android.api = 33
android.minapi = 24
android.ndk = 25b
android.python_version = 3.10
