[app]
title = Chess
package.name = mychess
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav
version = 1.0

# Ключевое исправление: жестко фиксируем Python 3.10.13 и версии библиотек
requirements = python3==3.10.13, hostpython3==3.10.13, kivy==2.3.0, cython==0.29.33

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.accept_sdk_license = True
android.api = 33
android.minapi = 24
android.ndk = 25b
# Дополнительная страховка для версии Python на Android
android.python_version = 3.10
