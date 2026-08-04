package com.superdl.launcher.gps

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

object GpsOverpassHelper {

    private const val USER_AGENT = "SuperDL/1.48 (vak-barat launcher; korosmezey.david.richard@gmail.com)"
    private const val RADIUS_METERS = 300
    private const val MAX_RESULTS = 35
    private const val HIGHWAY_FILTER =
        "^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|pedestrian|service|road)$"

    fun fetchNearbyIntersections(lat: Double, lon: Double, radiusM: Int = 120): List<IntersectionRaw> {
        val signalIntersections = fetchSignalIntersections(lat, lon, radiusM)
        val roadIntersections = fetchRoadGraphIntersections(lat, lon, radiusM)
        return (signalIntersections + roadIntersections)
            .distinctBy { "${it.latitude}_${it.longitude}" }
            .sortedBy { GpsRadarMath.distanceMeters(lat, lon, it.latitude, it.longitude) }
            .take(12)
    }

    fun fetchNearestStreetName(lat: Double, lon: Double, radiusM: Int = 45): String? {
        val query = """
            [out:json][timeout:10];
            way(around:$radiusM,$lat,$lon)[highway~"$HIGHWAY_FILTER"]["name"];
            out center 8;
        """.trimIndent().replace("\n", "")
        return try {
            val body = fetchPost("https://overpass-api.de/api/interpreter", "data=${URLEncoder.encode(query, "UTF-8")}")
            val elements = JSONObject(body).optJSONArray("elements") ?: JSONArray()
            var bestName: String? = null
            var bestDistance = Int.MAX_VALUE
            for (i in 0 until elements.length()) {
                val item = elements.optJSONObject(i) ?: continue
                if (item.optString("type") != "way") continue
                val tags = item.optJSONObject("tags") ?: continue
                val name = tags.optString("name").ifBlank { tags.optString("ref") }
                if (name.isBlank()) continue
                val center = item.optJSONObject("center")
                val wayLat = center?.optDouble("lat") ?: lat
                val wayLon = center?.optDouble("lon") ?: lon
                val distance = GpsRadarMath.distanceMeters(lat, lon, wayLat, wayLon)
                if (distance < bestDistance) {
                    bestDistance = distance
                    bestName = name
                }
            }
            bestName
        } catch (_: Exception) {
            null
        }
    }

    private fun fetchSignalIntersections(lat: Double, lon: Double, radiusM: Int): List<IntersectionRaw> {
        val query = """
            [out:json][timeout:15];
            (
              node(around:$radiusM,$lat,$lon)[highway=traffic_signals];
              node(around:$radiusM,$lat,$lon)[highway=stop];
              node(around:$radiusM,$lat,$lon)[highway=mini_roundabout];
              node(around:$radiusM,$lat,$lon)[junction=roundabout];
              node(around:$radiusM,$lat,$lon)[junction=circular];
            );
            out body;
            >;
            out tags;
        """.trimIndent().replace("\n", "")
        return try {
            val body = fetchPost("https://overpass-api.de/api/interpreter", "data=${URLEncoder.encode(query, "UTF-8")}")
            parseIntersections(JSONObject(body), lat, lon)
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun fetchRoadGraphIntersections(lat: Double, lon: Double, radiusM: Int): List<IntersectionRaw> {
        val query = """
            [out:json][timeout:15];
            way(around:$radiusM,$lat,$lon)[highway~"$HIGHWAY_FILTER"]["name"];
            (._;>;);
            out body;
        """.trimIndent().replace("\n", "")
        return try {
            val body = fetchPost("https://overpass-api.de/api/interpreter", "data=${URLEncoder.encode(query, "UTF-8")}")
            parseRoadGraphIntersections(JSONObject(body), lat, lon)
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun parseRoadGraphIntersections(json: JSONObject, userLat: Double, userLon: Double): List<IntersectionRaw> {
        val elements = json.optJSONArray("elements") ?: JSONArray()
        val nodes = mutableMapOf<Long, JSONObject>()
        val ways = mutableListOf<JSONObject>()
        for (i in 0 until elements.length()) {
            val item = elements.optJSONObject(i) ?: continue
            when (item.optString("type")) {
                "node" -> nodes[item.optLong("id")] = item
                "way" -> ways.add(item)
            }
        }
        val nodeStreetData = linkedMapOf<Long, LinkedHashMap<String, Float>>()
        for (way in ways) {
            val tags = way.optJSONObject("tags") ?: continue
            val name = tags.optString("name").ifBlank { tags.optString("ref") }
            if (name.isBlank()) continue
            val nodeRefs = way.optJSONArray("nodes") ?: continue
            for (index in 0 until nodeRefs.length()) {
                val nodeId = nodeRefs.optLong(index)
                val node = nodes[nodeId] ?: continue
                val nodeLat = node.optDouble("lat")
                val nodeLon = node.optDouble("lon")
                if (nodeLat == 0.0 && nodeLon == 0.0) continue
                val branchPoint = findBranchPoint(index, nodeRefs, nodes)
                val bearing = branchPoint?.let {
                    GpsRadarMath.bearingDegrees(nodeLat, nodeLon, it.first, it.second)
                }
                val streetMap = nodeStreetData.getOrPut(nodeId) { linkedMapOf() }
                if (bearing != null) {
                    streetMap[name] = bearing
                } else if (name !in streetMap) {
                    streetMap[name] = 0f
                }
            }
        }
        return nodeStreetData.mapNotNull { (nodeId, streetMap) ->
            if (streetMap.size < 2) return@mapNotNull null
            val node = nodes[nodeId] ?: return@mapNotNull null
            val nodeLat = node.optDouble("lat")
            val nodeLon = node.optDouble("lon")
            IntersectionRaw(
                latitude = nodeLat,
                longitude = nodeLon,
                streetNames = streetMap.keys.toList(),
                branchBearings = streetMap.filterValues { it != 0f }
            )
        }.distinctBy { "${it.latitude}_${it.longitude}" }
            .sortedBy { GpsRadarMath.distanceMeters(userLat, userLon, it.latitude, it.longitude) }
    }

    private fun parseIntersections(json: JSONObject, userLat: Double, userLon: Double): List<IntersectionRaw> {
        val elements = json.optJSONArray("elements") ?: JSONArray()
        val nodes = mutableMapOf<Long, JSONObject>()
        val ways = mutableMapOf<Long, JSONObject>()
        for (i in 0 until elements.length()) {
            val item = elements.optJSONObject(i) ?: continue
            when (item.optString("type")) {
                "node" -> nodes[item.optLong("id")] = item
                "way" -> ways[item.optLong("id")] = item
            }
        }
        val junctionNodes = nodes.values.filter { node ->
            val tags = node.optJSONObject("tags") ?: JSONObject()
            tags.has("highway") || tags.has("junction")
        }
        val result = mutableListOf<IntersectionRaw>()
        for (node in junctionNodes) {
            val nodeId = node.optLong("id")
            val nodeLat = node.optDouble("lat")
            val nodeLon = node.optDouble("lon")
            if (nodeLat == 0.0 && nodeLon == 0.0) continue
            val streetNames = linkedSetOf<String>()
            val branchBearings = linkedMapOf<String, Float>()
            for (way in ways.values) {
                val nodeRefs = way.optJSONArray("nodes") ?: continue
                val nodeIndex = (0 until nodeRefs.length()).firstOrNull { nodeRefs.optLong(it) == nodeId }
                    ?: continue
                val tags = way.optJSONObject("tags") ?: continue
                val highway = tags.optString("highway")
                if (highway !in HIGHWAY_ROAD_TYPES) continue
                val name = tags.optString("name").ifBlank { tags.optString("ref") }
                if (name.isBlank()) continue
                streetNames.add(name)
                val branchPoint = findBranchPoint(nodeIndex, nodeRefs, nodes)
                if (branchPoint != null) {
                    branchBearings[name] = GpsRadarMath.bearingDegrees(
                        nodeLat, nodeLon, branchPoint.first, branchPoint.second
                    )
                }
            }
            if (streetNames.size >= 2) {
                result.add(
                    IntersectionRaw(
                        latitude = nodeLat,
                        longitude = nodeLon,
                        streetNames = streetNames.toList(),
                        branchBearings = branchBearings
                    )
                )
            }
        }
        return result.distinctBy { "${it.latitude}_${it.longitude}" }
            .sortedBy { GpsRadarMath.distanceMeters(userLat, userLon, it.latitude, it.longitude) }
            .take(8)
    }

    private fun findBranchPoint(
        nodeIndex: Int,
        nodeRefs: JSONArray,
        nodes: Map<Long, JSONObject>
    ): Pair<Double, Double>? {
        val candidates = listOfNotNull(
            if (nodeIndex + 1 < nodeRefs.length()) nodes[nodeRefs.optLong(nodeIndex + 1)] else null,
            if (nodeIndex - 1 >= 0) nodes[nodeRefs.optLong(nodeIndex - 1)] else null
        )
        val branchNode = candidates.firstOrNull() ?: return null
        val lat = branchNode.optDouble("lat")
        val lon = branchNode.optDouble("lon")
        return if (lat != 0.0 || lon != 0.0) lat to lon else null
    }

    private val HIGHWAY_ROAD_TYPES = setOf(
        "motorway", "trunk", "primary", "secondary", "tertiary",
        "unclassified", "residential", "living_street", "pedestrian",
        "service", "road"
    )

    fun fetchNearbyCrossings(lat: Double, lon: Double, radiusM: Int = 20): List<CrossingPoint> {
        val query = """
            [out:json][timeout:10];
            (
              node(around:$radiusM,$lat,$lon)[highway=crossing];
              node(around:$radiusM,$lat,$lon)[crossing];
            );
            out body;
        """.trimIndent().replace("\n", "")
        val url = "https://overpass-api.de/api/interpreter"
        return try {
            val body = fetchPost(url, "data=${URLEncoder.encode(query, "UTF-8")}")
            val elements = JSONObject(body).optJSONArray("elements") ?: JSONArray()
            buildList {
                for (i in 0 until elements.length()) {
                    val item = elements.optJSONObject(i) ?: continue
                    if (item.optString("type") != "node") continue
                    val crossingLat = item.optDouble("lat")
                    val crossingLon = item.optDouble("lon")
                    if (crossingLat == 0.0 && crossingLon == 0.0) continue
                    add(CrossingPoint(crossingLat, crossingLon))
                }
            }.distinctBy { "${it.latitude}_${it.longitude}" }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun fetchNearbyPois(lat: Double, lon: Double): List<GpsPoiRaw> {
        val query = """
            [out:json][timeout:15];
            (
              node(around:$RADIUS_METERS,$lat,$lon)[shop];
              node(around:$RADIUS_METERS,$lat,$lon)[amenity];
              node(around:$RADIUS_METERS,$lat,$lon)[highway=bus_stop];
              node(around:$RADIUS_METERS,$lat,$lon)[public_transport=platform];
              node(around:$RADIUS_METERS,$lat,$lon)[railway=station];
              way(around:$RADIUS_METERS,$lat,$lon)[shop];
              way(around:$RADIUS_METERS,$lat,$lon)[amenity];
            );
            out center $MAX_RESULTS;
        """.trimIndent().replace("\n", "")
        val url = "https://overpass-api.de/api/interpreter"
        val body = fetchPost(url, "data=${URLEncoder.encode(query, "UTF-8")}")
        val elements = JSONObject(body).optJSONArray("elements") ?: JSONArray()
        val pois = mutableListOf<GpsPoiRaw>()
        for (i in 0 until elements.length()) {
            val item = elements.optJSONObject(i) ?: continue
            val tags = item.optJSONObject("tags") ?: continue
            if (!isRelevant(tags)) continue
            val name = tags.optString("name").ifBlank {
                tags.optString("brand").ifBlank { tags.optString("operator") }
            }
            if (name.isBlank()) continue
            val coords = extractCoordinates(item) ?: continue
            val category = categoryLabel(tags)
            val id = "${item.optString("type")}_${item.optLong("id")}"
            pois.add(
                GpsPoiRaw(
                    id = id,
                    name = name,
                    category = category,
                    latitude = coords.first,
                    longitude = coords.second
                )
            )
        }
        return pois.distinctBy { "${it.name}_${it.latitude}_${it.longitude}" }
    }

    private fun isRelevant(tags: JSONObject): Boolean {
        if (tags.has("shop")) return true
        if (tags.has("highway") && tags.optString("highway") == "bus_stop") return true
        if (tags.has("public_transport")) return true
        if (tags.has("railway")) return true
        val amenity = tags.optString("amenity")
        return amenity in RELEVANT_AMENITIES
    }

    private val RELEVANT_AMENITIES = setOf(
        "restaurant", "cafe", "fast_food", "pharmacy", "bank", "post_office",
        "pub", "bar", "dentist", "doctors", "clinic", "hospital", "library",
        "fuel", "marketplace", "food_court", "ice_cream", "bakery", "bicycle_parking"
    )

    private fun categoryLabel(tags: JSONObject): String {
        tags.optString("shop").takeIf { it.isNotBlank() }?.let { return shopLabel(it) }
        if (tags.optString("highway") == "bus_stop") return "megálló"
        if (tags.has("public_transport") || tags.has("railway")) return "tömegközlekedés"
        return amenityLabel(tags.optString("amenity"))
    }

    private fun shopLabel(value: String): String = when (value) {
        "supermarket", "convenience", "general", "mall", "department_store" -> "bolt"
        "bakery" -> "pékség"
        "clothes", "shoes", "hairdresser" -> "üzlet"
        "chemist" -> "gyógyszertár"
        else -> "bolt"
    }

    private fun amenityLabel(value: String): String = when (value) {
        "restaurant", "fast_food", "food_court" -> "étterem"
        "cafe", "ice_cream" -> "kávézó"
        "pharmacy" -> "gyógyszertár"
        "bank", "atm" -> "bank"
        "post_office" -> "posta"
        "fuel" -> "benzinkút"
        "hospital", "clinic", "doctors", "dentist" -> "egészségügy"
        "library" -> "könyvtár"
        "pub", "bar" -> "bár"
        "marketplace" -> "piac"
        else -> "létesítmény"
    }

    private fun extractCoordinates(item: JSONObject): Pair<Double, Double>? {
        val type = item.optString("type")
        if (type == "node") {
            val lat = item.optDouble("lat")
            val lon = item.optDouble("lon")
            if (lat != 0.0 || lon != 0.0) return lat to lon
        }
        val center = item.optJSONObject("center") ?: return null
        val lat = center.optDouble("lat")
        val lon = center.optDouble("lon")
        return if (lat != 0.0 || lon != 0.0) lat to lon else null
    }

    private fun fetchPost(url: String, formBody: String): String {
        // Stabilizált: több Overpass-tükör + újrapróbálkozás. Az url paramétert
        // már figyelmen kívül hagyjuk (a tükröket a GpsNetworkClient adja), hogy
        // a meglévő hívások változtatás nélkül működjenek.
        return GpsNetworkClient.postWithFailover(
            GpsNetworkClient.OVERPASS_MIRRORS, formBody
        ) ?: throw GpsRadarException("OpenStreetMap lekérdezés sikertelen.")
    }
}

data class CrossingPoint(
    val latitude: Double,
    val longitude: Double
)

class GpsRadarException(message: String) : Exception(message)