package com.superdl.launcher.storage

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject

object JsonPrefsHelper {

    private const val TAG = "SuperDL.JsonPrefs"

    fun readJsonArray(
        context: Context,
        prefsName: String,
        dataKey: String,
        schemaVersionKey: String,
        currentSchemaVersion: Int,
        migrate: ((JSONArray) -> JSONArray)? = null
    ): JSONArray {
        val prefs = context.getSharedPreferences(prefsName, Context.MODE_PRIVATE)
        val storedVersion = prefs.getInt(schemaVersionKey, 0)
        val raw = prefs.getString(dataKey, null)

        if (raw.isNullOrBlank()) {
            if (storedVersion < currentSchemaVersion) {
                prefs.edit().putInt(schemaVersionKey, currentSchemaVersion).apply()
            }
            return JSONArray()
        }

        return try {
            var array = JSONArray(raw)
            if (storedVersion < currentSchemaVersion) {
                array = migrate?.invoke(array) ?: array
                saveJsonArray(
                    context,
                    prefsName,
                    dataKey,
                    schemaVersionKey,
                    currentSchemaVersion,
                    array
                )
            }
            array
        } catch (e: Exception) {
            Log.e(TAG, "Corrupted JSON in $prefsName/$dataKey – resetting to empty", e)
            saveJsonArray(
                context,
                prefsName,
                dataKey,
                schemaVersionKey,
                currentSchemaVersion,
                JSONArray()
            )
            JSONArray()
        }
    }

    fun readJsonObject(
        context: Context,
        prefsName: String,
        dataKey: String,
        schemaVersionKey: String,
        currentSchemaVersion: Int,
        defaultIfMissing: JSONObject = JSONObject(),
        migrate: ((JSONObject) -> JSONObject)? = null
    ): JSONObject {
        val prefs = context.getSharedPreferences(prefsName, Context.MODE_PRIVATE)
        val storedVersion = prefs.getInt(schemaVersionKey, 0)
        val raw = prefs.getString(dataKey, null)

        if (raw.isNullOrBlank()) {
            if (storedVersion < currentSchemaVersion) {
                prefs.edit().putInt(schemaVersionKey, currentSchemaVersion).apply()
            }
            return JSONObject(defaultIfMissing.toString())
        }

        return try {
            var obj = JSONObject(raw)
            if (storedVersion < currentSchemaVersion) {
                obj = migrate?.invoke(obj) ?: obj
                saveJsonObject(
                    context,
                    prefsName,
                    dataKey,
                    schemaVersionKey,
                    currentSchemaVersion,
                    obj
                )
            }
            obj
        } catch (e: Exception) {
            Log.e(TAG, "Corrupted JSON object in $prefsName/$dataKey – resetting", e)
            saveJsonObject(
                context,
                prefsName,
                dataKey,
                schemaVersionKey,
                currentSchemaVersion,
                defaultIfMissing
            )
            JSONObject(defaultIfMissing.toString())
        }
    }

    fun saveJsonObject(
        context: Context,
        prefsName: String,
        dataKey: String,
        schemaVersionKey: String,
        schemaVersion: Int,
        obj: JSONObject
    ) {
        context.getSharedPreferences(prefsName, Context.MODE_PRIVATE)
            .edit()
            .putInt(schemaVersionKey, schemaVersion)
            .putString(dataKey, obj.toString())
            .apply()
    }

    fun saveJsonArray(
        context: Context,
        prefsName: String,
        dataKey: String,
        schemaVersionKey: String,
        schemaVersion: Int,
        array: JSONArray
    ) {
        context.getSharedPreferences(prefsName, Context.MODE_PRIVATE)
            .edit()
            .putInt(schemaVersionKey, schemaVersion)
            .putString(dataKey, array.toString())
            .apply()
    }
}