import Foundation

enum MenuLaunchStep: Equatable {
    case bootstrap
    case kickstart
}

func menuLaunchPlan(isLoaded: Bool) -> [MenuLaunchStep] {
    isLoaded ? [.kickstart] : [.bootstrap, .kickstart]
}
