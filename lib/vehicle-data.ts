export type VehicleRecord = {
  vin: string; serial: string; model: string; customer: string; salesperson: string;
  status: string; statusDate: string; projectedDelivery: string; chassisStart: string;
  dispatchDate: string; inServiceDate: string; buildLocation: string; salesOrder: string;
};

export const sampleVehicles: VehicleRecord[] = [
  { vin:"1FVHG3DV1VHXE0168", serial:"XE0168", model:"114SD", customer:"County Fleet", salesperson:"Douglas Austin", status:"Dealer Received", statusDate:"Jun 29 2026", projectedDelivery:"Jun 29 2026", chassisStart:"Jun 16 2026", dispatchDate:"Jun 25 2026", inServiceDate:"", buildLocation:"MTH", salesOrder:"01022026" },
  { vin:"1FVACWFC6VHXF5274", serial:"XF5274", model:"M2106", customer:"Municipal Fleet", salesperson:"Douglas Austin", status:"Scheduled", statusDate:"Aug 17 2026", projectedDelivery:"Sep 08 2026", chassisStart:"", dispatchDate:"", inServiceDate:"", buildLocation:"MTH", salesOrder:"020420262" },
  { vin:"4UZAAPFD7VCXM7651", serial:"XM7651", model:"Custom Chassis", customer:"Utility Fleet", salesperson:"", status:"Scheduled", statusDate:"Sep 21 2026", projectedDelivery:"", chassisStart:"", dispatchDate:"", inServiceDate:"", buildLocation:"", salesOrder:"" }
];

export function findVehicle(value: string) {
  const q = value.trim().toUpperCase();
  return sampleVehicles.find(v => v.vin === q || v.serial === q);
}
