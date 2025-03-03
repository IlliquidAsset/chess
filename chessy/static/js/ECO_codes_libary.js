/**
 * ECO Codes Library
 * 
 * Instead of duplicating ECO code data, this file fetches descriptions from the backend API.
 * This ensures a single source of truth for ECO codes data.
 */

// Cache for ECO descriptions to avoid repeated API calls
let ecoDescriptionsCache = null;
let isFetchingData = false;
let fetchPromise = null;

/**
 * Fetch all ECO descriptions from the server API
 * @returns {Promise<Object>} Promise resolving to an object mapping ECO codes to descriptions
 */
function fetchEcoDescriptions() {
    // Return existing promise if we're already fetching
    if (isFetchingData && fetchPromise) {
        return fetchPromise;
    }

    // If we already have the data cached, return it
    if (ecoDescriptionsCache) {
        return Promise.resolve(ecoDescriptionsCache);
    }

    // Start a new fetch
    isFetchingData = true;
    fetchPromise = fetch('/api/eco/all')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            ecoDescriptionsCache = data;
            isFetchingData = false;
            return data;
        })
        .catch(error => {
            console.error('Error fetching ECO descriptions:', error);
            isFetchingData = false;
            
            // Fallback data in case the API fails
            ecoDescriptionsCache = {
                "A00": "Irregular Openings",
                "B20": "Sicilian Defence",
                "C00": "French Defense",
                "D00": "Queen's Pawn Game",
                "E00": "Queen's Pawn, Indian Defenses"
            };
            return ecoDescriptionsCache;
        });

    return fetchPromise;
}

/**
 * Get a description for an ECO code
 * 
 * @param {string} ecoCode - The ECO code to look up (e.g., "A45")
 * @returns {Promise<string>} - Promise resolving to the description or "Unknown opening" if not found
 */
async function getEcoDescription(ecoCode) {
    if (!ecoCode) return "Unknown opening";
    
    // Standardize input (uppercase and trim)
    const standardCode = ecoCode.toString().trim().toUpperCase();
    
    try {
        const ecoDescriptions = await fetchEcoDescriptions();
        
        // Try to find exact match
        if (ecoDescriptions[standardCode]) {
            return ecoDescriptions[standardCode];
        }
        
        // Try to find closest match (first two chars)
        if (standardCode.length >= 2) {
            const prefix = standardCode.substring(0, 2);
            for (const code in ecoDescriptions) {
                if (code.startsWith(prefix)) {
                    return ecoDescriptions[code] + " (similar)";
                }
            }
        }
        
        // Try to find closest match (first char)
        if (standardCode.length >= 1) {
            const prefix = standardCode.substring(0, 1);
            for (const code in ecoDescriptions) {
                if (code.startsWith(prefix)) {
                    return ecoDescriptions[code] + " (general family)";
                }
            }
        }
    } catch (error) {
        console.error('Error in getEcoDescription:', error);
    }
    
    return "Unknown opening";
}

// For backward compatibility with synchronous usage
// Falls back to "Loading..." initially but will update once data is fetched
let syncEcoDescriptions = {
    "A00": "Loading ECO data...",
};

// Pre-fetch ECO descriptions for immediate use
fetchEcoDescriptions().then(data => {
    syncEcoDescriptions = data;
});

/**
 * Synchronous version for backward compatibility
 * Note: This may return "Loading..." initially
 */
function getEcoDescriptionSync(ecoCode) {
    if (!ecoCode) return "Unknown opening";
    
    // Standardize input (uppercase and trim)
    const standardCode = ecoCode.toString().trim().toUpperCase();
    
    // Try to find exact match
    if (syncEcoDescriptions[standardCode]) {
        return syncEcoDescriptions[standardCode];
    }
    
    // Try to find closest match (first two chars)
    if (standardCode.length >= 2) {
        const prefix = standardCode.substring(0, 2);
        for (const code in syncEcoDescriptions) {
            if (code.startsWith(prefix)) {
                return syncEcoDescriptions[code] + " (similar)";
            }
        }
    }
    
    return "Unknown opening";
}