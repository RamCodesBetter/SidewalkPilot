# Power

The car carries its own power. The drive motors are fed from a 3S LiPo through the
AT8236, while the compute boards (Pi 5, Jetson, Zero 2 W) run from high-output USB power
banks. Separating the noisy motor rail from the clean logic rail is the main goal of the
power design.

## Parts (Amazon)

- [INIU 27000mAh 140W Power Bank](https://www.amazon.com/INIU-27000mAh-Capacity-Powerbank-Compatible/dp/B0CB1FWNMK/ref=sr_1_3_mod_primary_new?crid=22FOBL7945FZM&dib=eyJ2IjoiMSJ9.meZepEu5vSz4vwHLYuqoo3Wk8qnZzXWmECTNX4Fy-hwokHJfR_rLAERXNYRFtflcpxZiXtyQoNX8zHQK-jS2xYdaUkUVVJN5nILgx954U5yQSRI_FGsMB-eooQbnzdHXm471o1A6WEBL9nH3LBbE3_j6cfYBtf4SxlXue5KzZ0L8OL4CNj23hupNeq0SVmsAxeG7KKm3b2lNio0926YPKOgj015yjHNnkRG3eSe8ECw.ibBDjkUT7hHlWrPVS5tOXojkxmcJoJ-ppJOM8oeBads&dib_tag=se&keywords=27000mah+140w&qid=1779577022&sbo=RZvfv%2F%2FHxDF%2BO5021pAnSA%3D%3D&sprefix=27000mah+140%2Caps%2C196&sr=8-3) — $79.99
- [Dual Battery Charger 1-6S/15S](https://www.amazon.com/Battery-Charger-Discharger-Screen-Balance/dp/B0DFWPXG2Q/ref=sr_1_8?dib=eyJ2IjoiMSJ9.kzkcy5FkdiED7IABXACV7pCj3VJGqOga5QXx5W1aZlZJ4brzLGrunkFJVaDHIFIS3BAQ8GpUKk0Xj6aEu_zVubYtptpX4ePANlZ7c_REsRhg9ZwZIEv7bjSItr8tgPaY_NN6p72YYgC2kMrNZ-UaflWaNoYpEAZkEaAcXCpSAOC431y2hikExFETz-ZhNQh5X_IOkBgR5gDv3G7M1qJ5fK33bq01hnXFQGvDzUvjIhBVdZg5NqbgQmjsSHa81q-UhZFPzIcld1Wd46llDgsgjVxT-GfqN3vzS49ayqTvmuk.cY7ofG1sAA1HQpxFycu766HcNPGyGZy5bGWzlqhSBko&dib_tag=se&keywords=dual%2Blipo%2Bcharger&qid=1779580280&sr=8-8&th=1) — $67.19
- [INIU 10000mAh 45W Power Bank](https://www.amazon.com/INIU-Portable-10000mAh-Essentials-Powerbank/dp/B0DQD35SQ4/ref=sr_1_1?crid=3EZM7ZXSIIYHR&dib=eyJ2IjoiMSJ9.PQH0AEJTF9npwSGLbl37ZJixwnZGEgdPfZSmiB5bW5Jzk8OJaQEdxmYa8VcexMyjU2nZxBJy_Le73m5NcbuoSHvumWaXRDD6vSNuMwZhn6R73-nOf_lKLV69v_l46rJh4GYlY3ICUgLDd70C-CZUIZr1zQEAtN477JrB37CEQaZ-tDm_Nl0MXoKomyZGojkRc_L8OTQW0sbK1YUkpCQX3c7v_xgexZ9qrB-u_MdpftCcK2cefdX-OD0mPzw4pGIvHRUh90TLcCzt7QOIlSmr9OjWIuIUVY7PvuEmBkHRvgM.96j1ymi3b_iU1LATDSZpMJ20_48qqIH_rN91wbLzJFw&dib_tag=se&keywords=10000mah%2B45W%2Biniu&qid=1779599391&s=electronics&sprefix=10000mah%2B45w%2Biniu%2Celectronics%2C191&sr=1-1&th=1) — $32.99
- [OVONIC 3S (11.1V) 5200mAh 80C](https://www.amazon.com/Battery-5200mAh-Connector-Helicopter-Airplane/dp/B09CTSFH36/ref=sr_1_6?crid=3H64SMSI4JUY&dib=eyJ2IjoiMSJ9.fiey7ED5TFt2eRNAPonxeN42prQGtRqAPbbpM-NzuVePYlXmslxIvnNNx6mv4vr0loRZGmkeqIjNElGIidLJu9YZQKTHuCo-hLo5UIqmu7_eIbqXm27rFV7K5sjKZNQn1-uU5bg_dEUkjex1EdxojbL47J-Vl00uzxogiBi0L121OsBcT-4qKB1BFXL4i6LafU0AI_-ELB8BV7S_XLPGoucb6SfPfjCpTYZVBuuOVNUyA2MMXjJQQSNmkY8iTrIGPjx0Ax3g4Gry4zYt2N68zfJeSOWlZpo8V_1oEjsrd_Q.gHxUD6G3WiwP4qgW87419c_bNutITqGr0lJD7I4weqs&dib_tag=se&keywords=3s+5200mah+lipo+battery&qid=1779577058&sprefix=3s+5200%2Caps%2C197&sr=8-6) — $23.19
- [10000uF Electrolytic Capacitors](https://www.amazon.com/dp/B0B758BH5L?psc=1&ref=cm_sw_r_cso_wa_apin_ct_73FXRE8SQ0B67B7WRX48&ref_=cm_sw_r_cso_wa_apin_ct_73FXRE8SQ0B67B7WRX48&social_share=cm_sw_r_cso_wa_apin_ct_73FXRE8SQ0B67B7WRX48) — $20.99
- [DROK DC Buck Converter](https://www.amazon.com/dp/B078Q1624B?ref=cm_sw_r_apin_ct_8W0Y8Q0X4RRRAV84QT9V&ref_=cm_sw_r_apin_ct_8W0Y8Q0X4RRRAV84QT9V&social_share=cm_sw_r_apin_ct_8W0Y8Q0X4RRRAV84QT9V&th=1) — $17.49
- [ATC/ATO 14AWG 10A AMP Fuses](https://www.amazon.com/dp/B07Q9PL4R6?ref=cm_sw_r_apin_ct_D0V24X6N2HC7GX465WYJ&ref_=cm_sw_r_apin_ct_D0V24X6N2HC7GX465WYJ&social_share=cm_sw_r_apin_ct_D0V24X6N2HC7GX465WYJ&th=1) — $15.99
- [OVONIC 2S (7.4V) 5200mAh 50C](https://www.amazon.com/OVONIC-5200mAh-Connector-Airplane-Helicopter/dp/B07JJ4Q65Z/ref=sr_1_8?crid=2NY4T275TZZDB&dib=eyJ2IjoiMSJ9.Rx8egGP6AfIhC3F36F5hy8xQM1pkK1UUD4O91eWDFWOL-Fw_cr1d5doCeeuUT0vxny-_y3O_y6AvLNoltS2AIQGWh2vtm95tvG8lWMBekmPIH12AGF8m8L9jMd0PL185T55rPshJNzElpkimOm41_aKg9BzsrzMo2SwYsfhdHiOs76vWOg0-0VAyHhjtpP_DZLezpPq5ng148Zxdwn0YhipqGVkLzsBOTkzVveF1asJP3y7wRCdIfSB99gM3_zZT0jaL8XqqjPpJpKtFuqUgeO5Y3tqUu8EIWLsFjBN5xiU.lwZBeg8mwdMMPBLFXqVR_ZQzgn0Lq4VTwuzRRhEU7AE&dib_tag=se&keywords=ovonic+2s+lipo+battery+5200mah+t+plug&qid=1779576913&sprefix=ovonic+2s+lipo+battery+5200mah+t+plu%2Caps%2C177&sr=8-8) — $13.29
## Power domains

- **Motor rail:** a 3S LiPo (11.1V; e.g. the OVONIC 3S 5200 mAh) feeds the AT8236 H-bridge
  and the drive motors. A DROK DC buck converter steps voltage down where a rail needs it,
  large 10000 uF electrolytic capacitors buffer the motor rail against current spikes, and
  ATC/ATO fuses protect against shorts.
- **Logic rail:** the compute boards run from USB power banks (a 27000 mAh 140W bank and a
  10000 mAh 45W bank), keeping the Pi/Jetson/Zero off the noisy motor supply.
- **Support gear:** a dual LiPo charger/discharger and a 2S LiPo are part of the battery kit
  for charging and bench work.

## How it works

- Motors and logic are on separate supplies to reduce how strongly motor start/brake current
  transients couple into the compute boards. Bulk capacitance can reduce rail excursions, a
  correctly configured buck converter regulates its downstream rail, and fuses limit fault
  current. None of those choices makes a brownout impossible.
- The Zero 2 W needs a stable supply, but a USB enumeration failure does not identify one
  cause. Power, cable integrity, the host port, and gadget state must be checked separately.

## Why this choice

- A 3S LiPo delivers the high current the drive motors need at a usable voltage, while USB
  power banks give the regulated, steady 5V the SBCs expect.
- Splitting the domains and adding capacitance/fusing is intended to reduce resets and contain
  electrical faults. A measured rail-voltage trace would be needed to attribute a particular
  reset or USB failure to power.

## Related pages

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
