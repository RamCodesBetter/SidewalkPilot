// mg24_yaw_firmware.ino — stream the 6-axis IMU's gyro (deg/s) over USB
//
// Board:   Seeed Studio XIAO MG24 Sense (built-in 6-axis IMU).
// Purpose: read the gyro, subtract the resting bias, and print all 3 axes as
//          CSV over USB serial so the Pi can (a) see which axis is YAW and
//          (b) read the live yaw rate for steering correction.
//
// SETUP in Arduino IDE:
//   1. Install the Seeed XIAO MG24 board package (Boards Manager).
//   2. Install the IMU library that matches the on-board chip — on the Sense
//      boards this is usually the LSM6DS3 ("Seeed Arduino LSM6DS3"). If your
//      board reports a different IMU in Seeed's wiki example, swap the include
//      + the three read calls below to that library; everything else stays.
//   3. Select the XIAO MG24 board + its port, Upload.
//
// IMPORTANT: keep the board STILL for ~1 second after it powers on — that's the
// gyro-bias calibration window.
//
// Output line (100 Hz):   gx,gy,gz      (deg/s, bias-corrected)

#include "Wire.h"
#include "LSM6DS3.h"            // <-- swap if your Sense uses a different IMU

LSM6DS3 imu(I2C_MODE, 0x6A);    // on-board IMU I2C address (confirm in Seeed's example: 0x6A or 0x6B)

float bias_x = 0.0, bias_y = 0.0, bias_z = 0.0;

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 3000) { }   // wait up to 3s for USB

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
