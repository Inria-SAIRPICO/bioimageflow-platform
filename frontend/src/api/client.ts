import axios from 'axios'

// Don't set a global Content-Type default — axios auto-detects body type
// (application/json for objects, multipart/form-data with boundary for
// FormData, etc.). A hardcoded default breaks FormData uploads.
export const api = axios.create()
