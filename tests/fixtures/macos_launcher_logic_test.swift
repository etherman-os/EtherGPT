import Foundation

let loadedPlan = menuLaunchPlan(isLoaded: true)
precondition(loadedPlan == [.kickstart], "a loaded but stopped menu must be kickstarted")

let unloadedPlan = menuLaunchPlan(isLoaded: false)
precondition(
    unloadedPlan == [.bootstrap, .kickstart],
    "an unloaded menu must be bootstrapped and then kickstarted"
)

print("macOS launcher logic tests passed")
