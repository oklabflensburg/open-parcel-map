import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Env } from './env.js'


const env = new Env()
env.injectLinkContent('.contact-mail', 'mailto:', '', env.contactMail, 'E-Mail')


const center = [54.79443515, 9.43205485]
const map = L.map('map', {
  zoomControl: false
}).setView(center, 13)

let currentLayer = null


function formatPlaceName(placeName) {
  const reversePlaceName = placeName.split(', ').reverse().join(' ')

  return reversePlaceName
}


function formatToAreaNumber(number) {
  let value = number
  let unit = 'ha'

  value = new Intl.NumberFormat('de-DE', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)

  return `${value} ${unit}`
}


function renderParcelMeta(data) {
  if (currentLayer) {
    map.removeLayer(currentLayer)
  }

  const geoJsonData = {
    'type': 'FeatureCollection',
    'features': [{
      'type': 'Feature',
      'geometry': {
        'type': data['geojson']['type'],
        'coordinates': data['geojson']['coordinates']
      },
      'properties': {}
    }]
  }

  currentLayer = L.geoJSON(geoJsonData, {
    style: {
      color: '#2463eb',
      weight: 2,
      fillOpacity: 0.1
    }
  }).addTo(map)

  map.fitBounds(currentLayer.getBounds())
  console.log(data)

  let detailOutput = ''

  if (data['parcel_number'] !== null) {
    detailOutput += `<li><strong>Flurstück</strong><br>${data['parcel_number']}</li>`
  }

  if (data['field_number'] !== null) {
    detailOutput += `<li><strong>Flur</strong><br>${data['field_number']}</li>`
  }

  if (data['cadastral_district_name'] !== null) {
    detailOutput += `<li><strong>Gemarkung</strong><br>${data['cadastral_district_name']}</li>`
  }

  if (data['cadastral_district_number'] !== null) {
    detailOutput += `<li><strong>Gemarkungsschlüssel</strong><br>${data['cadastral_district_number']}</li>`
  }

  if (data['municipality_name'] !== null) {
    const municipalityName = formatPlaceName(data['municipality_name'])
    detailOutput += `<li><strong>Gemeinde</strong><br>${municipalityName}</li>`
  }

  if (data['municipality_number'] !== null) {
    detailOutput += `<li><strong>Gemeindeschlüssel</strong><br>${data['municipality_number']}</li>`
  }

  if (data['district_name'] !== null) {
    const districtName = formatPlaceName(data['district_name'])
    detailOutput += `<li><strong>Kreis</strong><br>${districtName}</li>`
  }

  if (data['district_number'] !== null) {
    detailOutput += `<li><strong>Kreisschlüssel</strong><br>${data['district_number']}</li>`
  }

  if (data['area_hectares'] > 0) {
    const areaNumber = formatToAreaNumber(data['area_hectares'])
    detailOutput += `<li><strong>Fläche</strong><br>${areaNumber}</li>`
  }

  document.querySelector('#detailList').innerHTML = detailOutput
  document.querySelector('#sidebar').classList.remove('hidden')
  document.querySelector('#sidebar').classList.add('absolute')
  document.querySelector('#about').classList.add('hidden')
  document.querySelector('#sidebarContent').classList.remove('hidden')
}


function cleanParcelMeta() {
  if (currentLayer) {
    map.removeLayer(currentLayer)
  }

  document.querySelector('#detailList').innerHTML = ''
  document.querySelector('#sidebar').classList.add('hidden')
  document.querySelector('#sidebar').classList.remove('absolute')
  document.querySelector('#about').classList.remove('hidden')
  document.querySelector('#sidebarContent').classList.add('hidden')
}


function fetchParcelMeta(lat, lng) {
  const url = `https://api.oklabflensburg.de/administrative/v1/parcel?lat=${lat}&lng=${lng}`

  try {
    fetch(url, {
      method: 'GET'
    }).then((response) => response.json()).then((data) => {
      renderParcelMeta(data)
    }).catch(function (error) {
      cleanParcelMeta()
    })
  }
  catch {
    cleanParcelMeta()
  }
}


function updateScreen(screen) {
  const title = 'ALKIS® Flurstücksauskunft Schleswig-Holstein'

  if (screen === 'home') {
    document.querySelector('title').innerHTML = title
    document.querySelector('meta[property="og:title"]').setAttribute('content', title)
  }
}


function handleWindowSize() {
  const innerWidth = window.innerWidth

  return true
}


document.addEventListener('DOMContentLoaded', function () {
  L.tileLayer('https://tiles.oklabflensburg.de/sgm/{z}/{x}/{y}.png', {
    maxZoom: 20,
    maxNativeZoom: 20,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="dc:rights">OpenStreetMap</a> contributors'
  }).addTo(map)

  L.tileLayer('https://tiles.oklabflensburg.de/shalkislot/{z}/{x}/{y}.png', {
    maxZoom: 20,
    maxNativeZoom: 20,
    attribution: '&copy; <a href="https://www.schleswig-holstein.de/DE/landesregierung/ministerien-behoerden/LVERMGEOSH" target="_blank" rel="dc:rights">GeoBasis-DE/LVermGeo SH</a>/<a href="https://creativecommons.org/licenses/by/4.0" target="_blank" rel="dc:rights">CC BY 4.0</a>'
  }).addTo(map)

  map.on('click', function (e) {
    const lat = e.latlng.lat
    const lng = e.latlng.lng

    fetchParcelMeta(lat, lng)
  })

  document.querySelector('#sidebarContentCloseButton').addEventListener('click', function (e) {
    e.preventDefault()

    cleanParcelMeta()
  })

  document.querySelector('#sidebarCloseButton').addEventListener('click', function (e) {
    e.preventDefault()

    document.querySelector('#sidebar').classList.add('sm:h-dvh')
    document.querySelector('#sidebar').classList.remove('absolute', 'h-dvh')
    document.querySelector('#sidebarCloseWrapper').classList.add('hidden')

    history.replaceState({ screen: 'home' }, '', '/')
  })
})


window.onload = () => {
  if (!history.state) {
    history.replaceState({ screen: 'home' }, '', '/')
  }
}

// Handle popstate event when navigating back/forward in the history
window.addEventListener('popstate', (event) => {
  if (event.state && event.state.screen === 'home') {
    document.querySelector('#sidebar').classList.add('sm:h-dvh')
    document.querySelector('#sidebar').classList.remove('absolute', 'h-dvh')
    document.querySelector('#sidebarCloseWrapper').classList.add('hidden')
  }
  else {
    updateScreen('home')
  }
})


// Attach the resize event listener, but ensure proper function reference
window.addEventListener('resize', handleWindowSize)

// Trigger the function initially to handle the initial screen size
handleWindowSize()