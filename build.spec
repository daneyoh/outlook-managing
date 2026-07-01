# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    [os.path.join('00. BACKEND', 'app.py')],
    pathex=[os.path.join(os.getcwd(), '00. BACKEND')],
    binaries=[],
    datas=[
        (os.path.join('01. FRONTEND', 'ui.html'), '.'),
        ('widget.ico', '.'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'msal',
        'msal.application',
        'msal.authority',
        'win11toast',
        'state_io',
        'build_dashboard',
        'config',
        'fetch_mail',
        'fetch_loop',
        'weekly_review',
        'pythonnet',
        'clr',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OutlookWidget',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='widget.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OutlookWidget',
)
