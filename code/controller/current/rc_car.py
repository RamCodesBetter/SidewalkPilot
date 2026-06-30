#!/usr/bin/python3
"""RC car controller entrypoint.

No --model flag: model selection is on-device (the dashboard model page), and for
autonomy the heavy model runs on the Jetson ("Jon"). Just run `car`.
"""

if __name__ == "__main__":
    from rc_car_app.runtime import run

    run()
