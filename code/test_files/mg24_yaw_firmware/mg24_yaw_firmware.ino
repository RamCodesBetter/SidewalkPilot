// mg24_yaw_firmware.ino — stream the 6-axis IMU's gyro (deg/s) over USB
//
// Board:   Seeed Studio XIAO MG24 Sense (built-in 6-axis IMU).
// Purpose: read the gyro, subtract the resting bias, and print all 3 axes as
//          CSV over USB serial so the Pi can (a) see which axis is YAW and
//          (b) read the live yaw rate for steering correction.
//
// SETUP in Arduino IDE (confirmed from Seeed's XIAO MG24 wiki):
//   1. Settings -> "Additional boards manager URLs", add:
//        https://siliconlabs.github.io/arduino/package_arduinosilabs_index.json
//      then Tools -> Boards Manager -> search "Silicon Labs" -> Install.
//   2. Tools -> Board -> select the "XIAO MG24" variant.
//   3. Install the IMU library "Seeed_Arduino_LSM6DS3" — the MG24 Sense IMU is
//      an LSM6DS3TR-C at I2C 0x6A. It's NOT in Library Manager by default: get
//      the ZIP from github.com/Seeed-Studio/Seeed_Arduino_LSM6DS3 and add via
//      Sketch -> Include Library -> Add .ZIP Library. (This sketch already uses
//      its API: LSM6DS3 / readFloatGyroX/Y/Z.)
//   4. Select the port, Upload. Serial Monitor @ 115200 to verify.
//
// NOTE: the MG24 Sense POWER-GATES the IMU on pin PB1 — setup() drives PB1 HIGH
// to turn the IMU on (the wiki's deep-sleep demo drives it LOW to power down).
//
// IMPORTANT: keep the board STILL for ~1 second after it powers on — that's the
// gyro-bias calibration window.
//
// Output line (100 Hz):   gx,gy,gz      (deg/s, bias-corrected)

#include "Wire.h"
#include <LSM6DS3.h>            // Seeed_Arduino_LSM6DS3 (install via .ZIP — see header)

LSM6DS3 imu(I2C_MODE, 0x6A);    // MG24 Sense IMU = LSM6DS3TR-C at I2C 0x6A

float bias_x = 0.0, bias_y = 0.0, bias_z = 0.0;

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 3000) { }   // wait up to 3s for USB

  // The MG24 Sense power-gates the IMU on PB1 (wiki deep-sleep demo pulls it LOW
  // to power down). Drive HIGH so the IMU is powered before we talk to it.
  pinMode(PB1, OUTPUT);
  digitalWrite(PB1, HIGH);
  delay(50);

  if (imu.begin() != 0) {
    while (1) { Serial.println("ERR,imu_init_failed"); delay(500); }
  }

  // --- gyro bias calibration: board MUST be still ---
  const int N = 300;
  for (int i = 0; i < N; i++) {
    bias_x += imu.readFloatGyroX();
    bias_y += imu.readFloatGyroY();
    bias_z += imu.readFloatGyroZ();
    delay(3);
  }
  bias_x /= N; bias_y /= N; bias_z /= N;
  Serial.println("READY");      // the Pi can wait for this line
}

void loop() {
  float gx = imu.readFloatGyroX() - bias_x;   // deg/s
  float gy = imu.readFloatGyroY() - bias_y;
  float gz = imu.readFloatGyroZ() - bias_z;

  Serial.print(gx, 2); Serial.print(',');
  Serial.print(gy, 2); Serial.print(',');
  Serial.println(gz, 2);

  delay(10);                    // 100 Hz
}
