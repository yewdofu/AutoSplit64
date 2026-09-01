import as64core

from as64core.processing import Process


class ProcessXCam(Process):
    def __init__(self,):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("FADEIN")

    def execute(self):
        if as64core.fade_status in (as64core.FADEOUT_PARTIAL, as64core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        #if as64core.fade_status in (as64core.FADEIN_PARTIAL, as64core.FADEIN_COMPLETE):
            #return self.signals["FADEIN"]

        if as64core.incoming_split():
            if as64core.xcam_count == 0 and as64core.in_xcam and as64core.current_time - as64core.collection_time < 1:
                as64core.split()
            elif as64core.xcam_count == as64core.current_split().on_xcam:
                as64core.xcam_count = 0
                as64core.split()

        return self.signals["LOOP"]

    def on_transition(self):
        as64core.fps = 29.97
        as64core.enable_predictions(True)
        as64core.enable_xcam_count(True)

        super().on_transition()


class ProcessXCamStartUpSegment(Process):
    def __init__(self,):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("START")

        self._predictions = True

    def execute(self):
        if as64core.fade_status in (as64core.FADEOUT_PARTIAL, as64core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        # Base already applies the capture profile's configurable X-Cam
        # thresholds.  Reusing that result avoids a second, much narrower
        # hard-coded colour test that was especially fragile with compressed
        # or colour-shifted capture sources.
        if as64core.fadeout_count >= 1 and as64core.in_xcam:
            as64core.fps = 29.97
            as64core.enable_predictions(not self._predictions)
            as64core.split()
            as64core.fps = 10
            as64core.fadeout_count = 0
            as64core.set_in_game(True)
            return self.signals["START"]

        return self.signals["LOOP"]

    def on_transition(self):
        as64core.fps = 10
        as64core.enable_predictions(True)
        as64core.enable_xcam_count(True)

        super().on_transition()
