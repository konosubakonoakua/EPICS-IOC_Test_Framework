"""
FOR TESTING

Valid configuration script for a refelctometry beamline
"""

from ReflectometryServer import *

# This is the spacing between components
SPACING = 2


def get_beamline():
    """
    Returns: a beamline object describing the current beamline setup
    """
    # components
    s1 = Component("s1", PositionAndAngle(0.0, 1*SPACING, 90))
    s3 = Component("s3", PositionAndAngle(0.0, 3*SPACING, 90))
    detector = TiltingComponent("Detector", PositionAndAngle(0.0, 4*SPACING, 90))
    theta = ThetaComponent("ThetaComp", PositionAndAngle(0.0, 2*SPACING, 90), [detector])
    comps = [s1, theta, s3, detector]

    # BEAMLINE PARAMETERS
    slit1_pos = TrackingPosition("S1", s1, True)
    slit3_pos = TrackingPosition("S3", s3, True)
    theta_ang = AngleParameter("Theta", theta, True)
    detector_position = TrackingPosition("det_pos", detector, True)
    detector_angle = AngleParameter("det_ang", detector, True)

    params = [slit1_pos, theta_ang, slit3_pos, detector_position, detector_angle]

    # DRIVES
    drivers = [DisplacementDriver(s1, MotorPVWrapper("MOT:MTR0101")),
              DisplacementDriver(s3, MotorPVWrapper("MOT:MTR0102")),
              DisplacementDriver(detector, MotorPVWrapper("MOT:MTR0103")),
              AngleDriver(detector, MotorPVWrapper("MOT:MTR0104"))]

    # MODES
    nr_inits = {}
    nr_mode = BeamlineMode("NR", [param.name for param in params], nr_inits)
    modes = [nr_mode]

    beam_start = PositionAndAngle(0.0, 0.0, 0.0)
    bl = Beamline(comps, params, drivers, modes, beam_start)

    return bl
