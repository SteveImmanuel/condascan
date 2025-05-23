from enum import Enum

class ReturnCode(Enum): 
    EXECUTED = 0
    COMMAND_NOT_FOUND = 1
    UNHANDLED_ERROR = 2