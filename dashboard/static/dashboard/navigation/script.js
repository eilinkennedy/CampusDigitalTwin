// initialize map
const defaultCenter = [9.7270, 76.7260];
const map = L.map("map").setView(defaultCenter, 17);

// base map
L.tileLayer(
"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
{
attribution:"&copy; OpenStreetMap",
referrerPolicy:"origin"
}).addTo(map);

function collectCampusPoints(){
const points = [];

if(Array.isArray(routeCoords)){
routeCoords.forEach(p => points.push([p.lat, p.lng]));
}

if(Array.isArray(campusPaths)){
campusPaths.forEach(segment => {
if(Array.isArray(segment.coords)){
segment.coords.forEach(p => points.push([p.lat, p.lng]));
}
});
}

if(Array.isArray(buildingsData)){
buildingsData.forEach(b => points.push([b.lat, b.lng]));
}

return points.filter(p => Number.isFinite(p[0]) && Number.isFinite(p[1]));
}

const campusPoints = collectCampusPoints();
const campusBounds = campusPoints.length ? L.latLngBounds(campusPoints) : null;

function isWithinCampus(latlng){
if(!campusBounds || !campusBounds.isValid()) return true;
return campusBounds.pad(0.15).contains(latlng);
}

function removeYouAreHereLayer(layer){
if(!layer || typeof layer.getPopup !== "function") return;
const popup = layer.getPopup();
if(!popup || typeof popup.getContent !== "function") return;
const content = String(popup.getContent());
if(content.includes("You are here")){
map.removeLayer(layer);
}
}

map.on("layeradd", function(e){
removeYouAreHereLayer(e.layer);
});

setTimeout(function(){
map.eachLayer(function(layer){
removeYouAreHereLayer(layer);
});
}, 0);


// draw campus paths (grey)
campusPaths.forEach(function(segment){

const coords = segment.coords.map(p => [p.lat,p.lng]);

L.polyline(coords,{
color:"grey",
weight:3,
opacity:0.6
}).addTo(map);

});

// draw shortest route (blue)
let routeLayer = null;

if(routeCoords.length > 1){

const route = routeCoords.map(p => [p.lat,p.lng]);

routeLayer = L.polyline(route,{
color:"blue",
weight:6
}).addTo(map);

// start marker
L.marker(route[0]).addTo(map)
.bindPopup("Start");

// destination marker
L.marker(route[route.length-1]).addTo(map)
.bindPopup("Destination");

// zoom to route
map.fitBounds(routeLayer.getBounds(),{
padding:[40,40]
});

}

// building markers
function getOccupancyColor(percent){
if(percent <= 30) return "#22c55e";
if(percent <= 60) return "#facc15";
if(percent <= 80) return "#f97316";
return "#ef4444";
}

buildingsData.forEach(function(b){

L.circleMarker([b.lat,b.lng],{
radius:6,
fillColor:getOccupancyColor(b.occupancy_percent || 0),
color:"#000",
weight:1,
fillOpacity:0.8
})
.addTo(map)
.bindPopup(
`${b.name}<br>` +
`Predicted Occupancy: ${b.occupancy_percent || 0}%<br>` +
`Predicted Energy Consumption: ${b.predicted_energy || 0} kWh`
);

});

// predicted energy heatmap layer
if (Array.isArray(energyHeatmapData) && energyHeatmapData.length > 0) {
const maxEnergy = Math.max(...energyHeatmapData.map(p => p.energy), 1);
const heatPoints = energyHeatmapData.map(function(p){
const intensity = Math.max(0.15, p.energy / maxEnergy);
return [p.lat, p.lng, intensity];
});

if(typeof L.heatLayer === "function"){
L.heatLayer(heatPoints,{
radius:26,
blur:20,
maxZoom:17,
gradient:{
0.2:"#22c55e",
0.5:"#facc15",
0.9:"#ef4444"
}
}).addTo(map);
}

const sortedEnergies = energyHeatmapData
.map(p => p.energy)
.sort((a,b) => a-b);
const lowThreshold = sortedEnergies[Math.floor(sortedEnergies.length * 0.33)] || 0;
const highThreshold = sortedEnergies[Math.floor(sortedEnergies.length * 0.66)] || 0;

function getEnergyColor(value){
if(value <= lowThreshold) return "#22c55e";
if(value <= highThreshold) return "#facc15";
return "#ef4444";
}

energyHeatmapData.forEach(function(p){
const markerColor = getEnergyColor(p.energy);
const alertMessage = p.study_leave_alert
? `<br><strong>High-priority alert:</strong> ${p.study_leave_alert_reason}`
: "";
L.circleMarker([p.lat,p.lng],{
radius:7,
fillColor:markerColor,
color:"#0f172a",
weight:1,
fillOpacity:1
})
.addTo(map)
.bindPopup(`${p.building} (${p.building_type})<br>Predicted ${heatmapYear} energy: ${p.energy} kWh<br>Study-leave peak: ${p.study_leave_peak_kwh} kWh${alertMessage}`);
});
}
