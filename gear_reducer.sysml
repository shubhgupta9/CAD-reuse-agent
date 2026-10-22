// SysML v2 Model: Single-Stage Spur Gear Reducer
// Based on a typical industrial speed reducer (5:1 ratio)

package GearReducer {

    // ── Part Definitions ────────────────────────────────

    part def SpurGear {
        attribute partType : String;
        attribute function : String;
        attribute material : String;
        attribute teeth : Integer;
        attribute moduleMm : Real;
        attribute boreDiameterMm : Real;
        attribute faceWidthMm : Real;
        attribute pressureAngleDeg : Real;
    }

    part def Shaft {
        attribute partType : String;
        attribute function : String;
        attribute material : String;
        attribute diameterMm : Real;
        attribute lengthMm : Real;
        attribute keyway : String;
    }

    part def Bearing {
        attribute partType : String;
        attribute function : String;
        attribute material : String;
        attribute boreDiameterMm : Real;
        attribute outerDiameterMm : Real;
        attribute widthMm : Real;
        attribute loadRatingKn : Real;
    }

    part def Housing {
        attribute partType : String;
        attribute function : String;
        attribute material : String;
        attribute lengthMm : Real;
        attribute widthMm : Real;
        attribute heightMm : Real;
        attribute mounting : String;
    }

    part def Fastener {
        attribute partType : String;
        attribute function : String;
        attribute material : String;
        attribute threadSize : String;
        attribute lengthMm : Real;
        attribute headType : String;
    }

    part def Seal {
        attribute partType : String;
        attribute function : String;
        attribute material : String;
        attribute shaftDiameterMm : Real;
        attribute boreDiameterMm : Real;
    }

    part def Key {
        attribute partType : String;
        attribute function : String;
        attribute material : String;
        attribute widthMm : Real;
        attribute heightMm : Real;
        attribute lengthMm : Real;
    }

    // ── Assembly ────────────────────────────────────────

    part gearReducerAssembly : GearReducerSystem {

        part inputGear : SpurGear {
            :>> partType = "Spur Gear";
            :>> function = "Transmit torque from input shaft, high-speed pinion";
            :>> material = "Steel";
            :>> teeth = 20;
            :>> moduleMm = 2.0;
            :>> boreDiameterMm = 15.0;
            :>> faceWidthMm = 20.0;
            :>> pressureAngleDeg = 20.0;
        }

        part outputGear : SpurGear {
            :>> partType = "Spur Gear";
            :>> function = "Transmit torque to output shaft, low-speed driven gear";
            :>> material = "Steel";
            :>> teeth = 100;
            :>> moduleMm = 2.0;
            :>> boreDiameterMm = 30.0;
            :>> faceWidthMm = 20.0;
            :>> pressureAngleDeg = 20.0;
        }

        part inputShaft : Shaft {
            :>> partType = "Shaft";
            :>> function = "Carry input gear and transmit torque from motor";
            :>> material = "Steel";
            :>> diameterMm = 15.0;
            :>> lengthMm = 120.0;
            :>> keyway = "5mm parallel key";
        }

        part outputShaft : Shaft {
            :>> partType = "Shaft";
            :>> function = "Carry output gear and deliver reduced-speed torque";
            :>> material = "Steel";
            :>> diameterMm = 30.0;
            :>> lengthMm = 150.0;
            :>> keyway = "8mm parallel key";
        }

        part inputBearingA : Bearing {
            :>> partType = "Bearing";
            :>> function = "Support input shaft, radial load";
            :>> material = "Steel";
            :>> boreDiameterMm = 15.0;
            :>> outerDiameterMm = 35.0;
            :>> widthMm = 11.0;
            :>> loadRatingKn = 5.6;
        }

        part inputBearingB : Bearing {
            :>> partType = "Bearing";
            :>> function = "Support input shaft, radial load";
            :>> material = "Steel";
            :>> boreDiameterMm = 15.0;
            :>> outerDiameterMm = 35.0;
            :>> widthMm = 11.0;
            :>> loadRatingKn = 5.6;
        }

        part outputBearingA : Bearing {
            :>> partType = "Bearing";
            :>> function = "Support output shaft, radial and axial load";
            :>> material = "Steel";
            :>> boreDiameterMm = 30.0;
            :>> outerDiameterMm = 62.0;
            :>> widthMm = 16.0;
            :>> loadRatingKn = 13.3;
        }

        part outputBearingB : Bearing {
            :>> partType = "Bearing";
            :>> function = "Support output shaft, radial and axial load";
            :>> material = "Steel";
            :>> boreDiameterMm = 30.0;
            :>> outerDiameterMm = 62.0;
            :>> widthMm = 16.0;
            :>> loadRatingKn = 13.3;
        }

        part housingBody : Housing {
            :>> partType = "Housing";
            :>> function = "Enclose and protect gear train, provide mounting";
            :>> material = "Aluminum";
            :>> lengthMm = 200.0;
            :>> widthMm = 150.0;
            :>> heightMm = 120.0;
            :>> mounting = "M8 bolts, 4-point foot mount";
        }

        part housingBolt1 : Fastener {
            :>> partType = "Screw";
            :>> function = "Fasten housing halves together";
            :>> material = "Steel";
            :>> threadSize = "M6";
            :>> lengthMm = 25.0;
            :>> headType = "Socket Head Cap";
        }

        part mountingBolt1 : Fastener {
            :>> partType = "Screw";
            :>> function = "Secure housing to machine base";
            :>> material = "Steel";
            :>> threadSize = "M8";
            :>> lengthMm = 30.0;
            :>> headType = "Hex Head";
        }

        part inputSeal : Seal {
            :>> partType = "Seal";
            :>> function = "Prevent lubricant leakage at input shaft";
            :>> material = "Rubber";
            :>> shaftDiameterMm = 15.0;
            :>> boreDiameterMm = 35.0;
        }

        part outputSeal : Seal {
            :>> partType = "Seal";
            :>> function = "Prevent lubricant leakage at output shaft";
            :>> material = "Rubber";
            :>> shaftDiameterMm = 30.0;
            :>> boreDiameterMm = 62.0;
        }

        part inputKey : Key {
            :>> partType = "Key";
            :>> function = "Lock input gear to input shaft";
            :>> material = "Steel";
            :>> widthMm = 5.0;
            :>> heightMm = 5.0;
            :>> lengthMm = 18.0;
        }

        part outputKey : Key {
            :>> partType = "Key";
            :>> function = "Lock output gear to output shaft";
            :>> material = "Steel";
            :>> widthMm = 8.0;
            :>> heightMm = 7.0;
            :>> lengthMm = 25.0;
        }
    }
}
