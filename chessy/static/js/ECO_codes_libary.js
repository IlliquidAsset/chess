/**
 * ECO Codes Library
 * 
 * Provides descriptions for Encyclopedia of Chess Openings (ECO) codes
 * to enhance the user experience in the Chessy application.
 */

const ecoCodesLibrary = {
    // A-series: Flank Openings
    "A00": "Irregular Openings (including Polish Opening, Sokolsky Opening)",
    "A01": "Nimzovich-Larsen Attack",
    "A02": "Bird's Opening (1.f4)",
    "A03": "Bird's Opening, 1...d5",
    "A04": "Reti Opening",
    "A05": "Reti Opening, King's Indian Attack",
    "A06": "Reti Opening, 1...d5",
    "A07": "Reti Opening, King's Indian Attack (Barcza System)",
    "A08": "Reti Opening, King's Indian Attack",
    "A09": "Reti Opening, Advance Variation",
    "A10": "English Opening",
    "A11": "English Opening, Caro-Kann Defensive System",
    "A12": "English Opening, Caro-Kann Defensive System",
    "A13": "English Opening, Agincourt Defense",
    "A14": "English Opening, Neo-Catalan Declined",
    "A15": "English Opening, Anglo-Indian Defense",
    "A20": "English Opening, King's English Variation",
    "A30": "English Opening, Symmetrical Variation",
    "A40": "Queen's Pawn Opening (1.d4 with various defenses)",
    "A41": "Queen's Pawn Opening (various Black defenses)",
    "A43": "Old Benoni Defense",
    "A45": "Queen's Pawn Game",
    "A46": "Queen's Pawn Game, Torre Attack",
    "A48": "King's Indian, East Indian Defense",
    "A50": "Queen's Pawn Game, Black Knights' Tango",
    "A51": "Budapest Gambit Declined",
    "A56": "Benoni Defense",
    "A57": "Benko Gambit",
    "A60": "Benoni Defense, Modern Variation",
    "A80": "Dutch Defense",
    
    // B-series: Semi-Open Games
    "B00": "Uncommon King's Pawn Opening",
    "B01": "Scandinavian Defense",
    "B02": "Alekhine's Defense",
    "B06": "Robatsch (Modern) Defense",
    "B07": "Pirc Defense",
    "B10": "Caro-Kann Defense",
    "B12": "Caro-Kann Defense",
    "B13": "Caro-Kann, Exchange Variation",
    "B20": "Sicilian Defense",
    "B21": "Sicilian, Grand Prix Attack",
    "B22": "Sicilian, Alapin Variation (2.c3)",
    "B23": "Sicilian, Closed",
    "B27": "Sicilian Defense, Various",
    "B29": "Sicilian, Nimzovich-Rubinstein Variation",
    "B30": "Sicilian Defense, Old Sicilian",
    "B40": "Sicilian Defense",
    
    // C-series: Open Games and Queen's Pawn Games
    "C00": "French Defense",
    "C01": "French, Exchange Variation",
    "C02": "French, Advance Variation",
    "C10": "French, Paulsen Variation",
    "C20": "King's Pawn Game",
    "C30": "King's Gambit",
    "C40": "King's Knight Opening",
    "C41": "Philidor Defense",
    "C42": "Petrov's Defense",
    "C44": "King's Pawn Game",
    "C45": "Scotch Game",
    "C46": "Three Knights Opening",
    "C50": "Giuoco Piano",
    "C55": "Two Knights Defense",
    "C60": "Ruy Lopez (Spanish Opening)",
    "C65": "Ruy Lopez, Berlin Defense",
    "C68": "Ruy Lopez, Exchange Variation",
    "C70": "Ruy Lopez",
    
    // D-series: Closed Games and Indian Defenses
    "D00": "Queen's Pawn Game, Mason Variation",
    "D01": "Richter-Veresov Attack",
    "D02": "Queen's Pawn Game, 2.Nf3",
    "D05": "Queen's Pawn Game, Colle System (Zukertort Variation)",
    "D06": "Queen's Gambit Declined",
    "D07": "Queen's Gambit Declined, Chigorin Defense",
    "D10": "Queen's Gambit Declined Slav Defense",
    "D11": "Queen's Gambit Declined Slav Defense, 3.Nf3",
    "D20": "Queen's Gambit Accepted",
    "D30": "Queen's Gambit Declined",
    "D31": "Queen's Gambit Declined, Queen's Knight Variation",
    "D40": "Queen's Gambit Declined, Semi-Tarrasch Defense",
    "D43": "Queen's Gambit Declined, Semi-Slav",
    "D50": "Queen's Gambit Declined, 4.Bg5",
    "D60": "Queen's Gambit Declined, Orthodox Defense",
    "D70": "Neo-Grünfeld Defense",
    "D80": "Grünfeld Defense",
    "D85": "Grünfeld, Exchange Variation",
    "D90": "Grünfeld, Three Knights Variation",
    
    // E-series: Indian Defenses
    "E00": "Queen's Pawn Game, Non-standard replies",
    "E01": "Catalan Opening",
    "E10": "Queen's Pawn Game, Blumenfeld Counter Gambit",
    "E11": "Bogo-Indian Defense",
    "E12": "Queen's Indian Defense",
    "E20": "Nimzo-Indian Defense",
    "E30": "Nimzo-Indian, Leningrad Variation",
    "E40": "Nimzo-Indian, 4.e3",
    "E50": "Nimzo-Indian, 4.e3 e8g8, 5.Nf3, without ...d5",
    "E60": "King's Indian Defense",
    "E70": "King's Indian, 4.e4",
    "E80": "King's Indian, Sämisch Variation",
    "E90": "King's Indian, 5.Nf3"
};

/**
 * Get a description for an ECO code
 * 
 * @param {string} ecoCode - The ECO code to look up (e.g., "A45")
 * @returns {string} - Description of the opening or "Unknown opening" if not found
 */
function getEcoDescription(ecoCode) {
    if (!ecoCode) return "Unknown opening";
    
    // Standardize input (uppercase and trim)
    const standardCode = ecoCode.toString().trim().toUpperCase();
    
    // Try to find exact match
    if (ecoCodesLibrary[standardCode]) {
        return ecoCodesLibrary[standardCode];
    }
    
    // Try to find closest match (first two chars)
    if (standardCode.length >= 2) {
        const prefix = standardCode.substring(0, 2);
        for (const code in ecoCodesLibrary) {
            if (code.startsWith(prefix)) {
                return ecoCodesLibrary[code] + " (similar)";
            }
        }
    }
    
    // Try to find closest match (first char)
    if (standardCode.length >= 1) {
        const prefix = standardCode.substring(0, 1);
        for (const code in ecoCodesLibrary) {
            if (code.startsWith(prefix)) {
                return ecoCodesLibrary[code] + " (general family)";
            }
        }
    }
    
    return "Unknown opening";
}