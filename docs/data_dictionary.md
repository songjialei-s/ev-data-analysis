# Real charging-order data dictionary

The dictionary documents the 53 source columns without publishing any source values. Chinese platform labels are retained in the source reader; analytical aliases can be introduced downstream.

| Field group | Source fields | Meaning and publication rule |
| --- | --- | --- |
| Order identity | `orderType`, `orderNum`, `businessNum` | Order category, business primary key and internal transaction number. Never publish `businessNum`; do not publish row-level real `orderNum`. |
| Station/device | `stationName`, `plugNum`, `plugType` | Charging location, connector identifier and connector type. Station/device detail requires business approval before publication. |
| Application/start | `app`, `startType`, `chargeStatus` | Source application, start channel and charging status. |
| User/company | `userNum`, `companyName`, `deptName` | User and organization identifiers. Sensitive; remove raw values. |
| Card | `cardNum` | Charging/payment card identifier. Sensitive; remove raw values. |
| Vehicle | `carLicense`, `carVin`, `carMyLicense`, `carDept` | License plate, VIN and internal vehicle metadata. Sensitive; remove raw values. |
| Cloud time | `chargeBegin`, `chargeEnd`, `chargeTimeMinute` | Canonical analysis timestamps and reported charging duration. |
| Native time | `chargeBeginNative`, `chargeEndNative`, `chargeTimeNative` | Terminal-side auxiliary timestamps and duration; not used as the hard cleaning clock. |
| Battery state | `beginSOC`, `endSOC` | Battery state of charge at start and end. Missing/reversed values are flagged, not deleted. |
| Stop information | `endReason` | Session stop reason. Operational exception reasons are retained for reliability analysis. |
| Energy | `chargingPower` | Delivered energy in kWh despite the source label using “Power”. Non-positive values are operational flags when duration is valid. |
| Charges | `chargingPay`, `chargingelectricityPay`, `chargingServicePay` | Gross amount, electricity amount and service amount. Used for fee-conservation checks. |
| Settlement | `chargingPayActual`, `chargingDiscount`, `payTime`, `payMethod`, `payStatus` | Actual payment, discount and payment metadata. Unpaid rows are retained. |
| Peak period | `peakElectricityPower`, `peakElectricityBill`, `peakServiceBill` | Peak-period energy, electricity fee and service fee. |
| Super-peak period | `superpeakElectricityPower`, `superpeakElectricityBill`, `superpeakServiceBill` | Super-peak-period components. |
| Valley period | `valleyElectricityPower`, `valleyElectricityBill`, `valleyServiceBill` | Valley-period components. |
| Normal period | `normalElectricityPower`, `normalElectricityBill`, `normalServiceBill` | Normal/flat-period components. |
| Secondary peak | `peak2ElectricityPower`, `peak2ElectricityBill`, `peak2ServiceBill` | Additional peak-period components. |
| Deep valley | `deepvalleyElectricityPower`, `deepvalleyElectricityBill`, `deepvalleyServiceBill` | Deep-valley-period components. |

Derived private-fact flags include `is_zero_energy_session`, `is_paid`, `is_soc_missing`, `is_soc_reverse`, `is_native_detail_missing` and `fee_balance_ok`. Salted `user_key` and `vehicle_key` support longitudinal analysis without exporting direct identifiers.
