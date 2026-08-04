# SuperDL ProGuard / R8 rules (release minify előkészítés)

-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod

# Launcher core
-keep class com.superdl.launcher.** { *; }

# TensorFlow Lite – modell betöltés és interpreter
-keep class org.tensorflow.lite.** { *; }
-keep class org.tensorflow.lite.support.** { *; }
-dontwarn org.tensorflow.lite.**

# ML Kit (QR, OCR)
-keep class com.google.mlkit.** { *; }
-dontwarn com.google.mlkit.**

# CameraX
-keep class androidx.camera.** { *; }
-dontwarn androidx.camera.**

# Speech / TTS reflection
-keep class android.speech.** { *; }

# Hidden API bypass (hotspot / tethering reflection)
-keep class org.lsposed.hiddenapibypass.** { *; }

# BroadcastReceiver / Service manifest entries
-keepclasseswithmembers class * {
    public <init>(...);
}
-keepclassmembers class * extends android.content.BroadcastReceiver {
    public void onReceive(android.content.Context, android.content.Intent);
}
-keepclassmembers class * extends android.app.Service {
    public void onStartCommand(android.content.Intent, int, int);
}

# PDFBox optional JPEG2000 + BouncyCastle LDAP (not used on Android)
-dontwarn com.gemalto.jp2.JP2Decoder
-dontwarn com.gemalto.jp2.JP2Encoder
-dontwarn javax.naming.NamingEnumeration
-dontwarn javax.naming.NamingException
-dontwarn javax.naming.directory.Attribute
-dontwarn javax.naming.directory.Attributes
-dontwarn javax.naming.directory.DirContext
-dontwarn javax.naming.directory.InitialDirContext
-dontwarn javax.naming.directory.SearchControls
-dontwarn javax.naming.directory.SearchResult

# Tink KeysDownloader opcionalis Google HTTP kliense (nem hasznaljuk)
-dontwarn com.google.api.client.http.HttpTransport
-dontwarn com.google.api.client.http.javanet.NetHttpTransport$Builder
-dontwarn com.google.api.client.http.javanet.NetHttpTransport