package com.superdl.launcher.shopping

import android.content.Context
import com.superdl.launcher.storage.JsonPrefsHelper
import org.json.JSONArray
import org.json.JSONObject

object ShoppingListStore {

    private const val PREFS = "shopping_lists"
    private const val KEY_LISTS = "lists"
    private const val KEY_LISTS_SCHEMA = "lists_schema"
    private const val SCHEMA_VERSION = 1
    private const val KEY_ACTIVE = "active_list"
    private const val MAX_LISTS = 20
    private const val MAX_ITEMS = 100

    fun getListNames(context: Context): List<String> {
        val lists = loadLists(context)
        return lists.keys.sorted()
    }

    fun getActiveListName(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_ACTIVE, null)
            ?.takeIf { getListNames(context).contains(it) }

    fun setActiveListName(context: Context, name: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ACTIVE, name.trim())
            .apply()
    }

    fun getItems(context: Context, listName: String): List<ShoppingItem> =
        loadLists(context)[listName] ?: emptyList()

    fun getActiveItems(context: Context): List<ShoppingItem> {
        val name = getActiveListName(context) ?: return emptyList()
        return getItems(context, name)
    }

    fun createList(context: Context, name: String): Boolean {
        val trimmed = name.trim()
        if (trimmed.isBlank()) return false
        val lists = loadLists(context).toMutableMap()
        if (lists.containsKey(trimmed)) return true
        if (lists.size >= MAX_LISTS) return false
        lists[trimmed] = emptyList()
        saveLists(context, lists)
        setActiveListName(context, trimmed)
        return true
    }

    fun renameList(context: Context, oldName: String, newName: String): Boolean {
        val trimmed = newName.trim()
        if (trimmed.isBlank() || trimmed == oldName) return false
        val lists = loadLists(context).toMutableMap()
        val items = lists.remove(oldName) ?: return false
        if (lists.containsKey(trimmed)) return false
        lists[trimmed] = items
        saveLists(context, lists)
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY_ACTIVE, null) == oldName) {
            prefs.edit().putString(KEY_ACTIVE, trimmed).apply()
        }
        return true
    }

    fun deleteList(context: Context, name: String): Boolean {
        val lists = loadLists(context).toMutableMap()
        if (lists.remove(name) == null) return false
        saveLists(context, lists)
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY_ACTIVE, null) == name) {
            prefs.edit().remove(KEY_ACTIVE).apply()
        }
        return true
    }

    fun addItem(context: Context, listName: String, itemName: String, priceHuf: Int? = null): ShoppingItem? {
        val trimmed = itemName.trim()
        if (trimmed.isBlank()) return null
        val lists = loadLists(context).toMutableMap()
        val items = lists[listName]?.toMutableList() ?: mutableListOf()
        if (items.size >= MAX_ITEMS) return null
        val nextId = (items.maxOfOrNull { it.id } ?: 0) + 1
        val item = ShoppingItem(nextId, trimmed, priceHuf = priceHuf)
        items.add(item)
        lists[listName] = items
        saveLists(context, lists)
        return item
    }

    fun updateItemName(context: Context, listName: String, itemId: Int, newName: String): ShoppingItem? {
        val trimmed = newName.trim()
        if (trimmed.isBlank()) return null
        val lists = loadLists(context).toMutableMap()
        val items = lists[listName]?.toMutableList() ?: return null
        val idx = items.indexOfFirst { it.id == itemId }
        if (idx < 0) return null
        val updated = items[idx].copy(name = trimmed)
        items[idx] = updated
        lists[listName] = items
        saveLists(context, lists)
        return updated
    }

    fun updateItemPrice(context: Context, listName: String, itemId: Int, priceHuf: Int?): ShoppingItem? {
        val lists = loadLists(context).toMutableMap()
        val items = lists[listName]?.toMutableList() ?: return null
        val idx = items.indexOfFirst { it.id == itemId }
        if (idx < 0) return null
        val updated = items[idx].copy(priceHuf = priceHuf)
        items[idx] = updated
        lists[listName] = items
        saveLists(context, lists)
        return updated
    }

    fun removeItem(context: Context, listName: String, itemId: Int): Boolean {
        val lists = loadLists(context).toMutableMap()
        val items = lists[listName]?.toMutableList() ?: return false
        val removed = items.removeAll { it.id == itemId }
        if (!removed) return false
        lists[listName] = items
        saveLists(context, lists)
        return true
    }

    fun toggleChecked(context: Context, listName: String, itemId: Int): ShoppingItem? {
        val lists = loadLists(context).toMutableMap()
        val items = lists[listName]?.toMutableList() ?: return null
        val idx = items.indexOfFirst { it.id == itemId }
        if (idx < 0) return null
        val updated = items[idx].copy(checked = !items[idx].checked)
        items[idx] = updated
        lists[listName] = items
        saveLists(context, lists)
        return updated
    }

    fun totalPriceHuf(items: List<ShoppingItem>): Int =
        items.mapNotNull { it.priceHuf }.sum()

    fun speakTotal(items: List<ShoppingItem>): String {
        val priced = items.count { it.priceHuf != null }
        if (priced == 0) return "Nincs ár megadva egyetlen tételhez sem."
        val total = totalPriceHuf(items)
        return "Árösszesítő: $total forint, $priced áras tétel alapján."
    }

    private fun loadLists(context: Context): Map<String, List<ShoppingItem>> {
        val root = JsonPrefsHelper.readJsonObject(
            context = context,
            prefsName = PREFS,
            dataKey = KEY_LISTS,
            schemaVersionKey = KEY_LISTS_SCHEMA,
            currentSchemaVersion = SCHEMA_VERSION
        )
        val result = mutableMapOf<String, List<ShoppingItem>>()
        root.keys().forEach { listName ->
            val arr = root.optJSONArray(listName) ?: JSONArray()
            val items = mutableListOf<ShoppingItem>()
            for (i in 0 until arr.length()) {
                val obj = arr.optJSONObject(i) ?: continue
                val price = obj.optInt("priceHuf", -1).takeIf { it >= 0 }
                items.add(
                    ShoppingItem(
                        id = obj.optInt("id", i + 1),
                        name = obj.optString("name", ""),
                        checked = obj.optBoolean("checked", false),
                        priceHuf = price
                    )
                )
            }
            result[listName] = items.filter { it.name.isNotBlank() }
        }
        return result
    }

    private fun saveLists(context: Context, lists: Map<String, List<ShoppingItem>>) {
        val root = JSONObject()
        lists.forEach { (name, items) ->
            val arr = JSONArray()
            items.forEach { item ->
                val obj = JSONObject()
                    .put("id", item.id)
                    .put("name", item.name)
                    .put("checked", item.checked)
                item.priceHuf?.let { obj.put("priceHuf", it) }
                arr.put(obj)
            }
            root.put(name, arr)
        }
        JsonPrefsHelper.saveJsonObject(
            context,
            PREFS,
            KEY_LISTS,
            KEY_LISTS_SCHEMA,
            SCHEMA_VERSION,
            root
        )
    }
}