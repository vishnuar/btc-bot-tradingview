import MetaTrader5 as mt5
from flask import Flask, request, jsonify

print("MetaTrader5 package author: ",mt5.__author__)
print("MetaTrader5 package version: ",mt5.__version__)

# === CONFIGURATION ===
MT5_ACCOUNT =   # Integer Replace with your Exness account number
MT5_PASSWORD = ""  # Replace with your Exness password
MT5_SERVER = ""  # Check your broker details
DEVIATION = 10  # Price slippage in points
MAGIC_NUMBER = 123456
TRADE_LOG = []  # To track open trades
btc_cnter = 0
xau_cnter = 0


# === FLASK SERVER ===
app = Flask(__name__)

# === INITIALIZE & LOGIN TO MT5 ===
def connect_mt5():
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return False

    authorized = mt5.login(MT5_ACCOUNT, password=MT5_PASSWORD, server=MT5_SERVER)
    if not authorized:
        print("Failed to login to MT5. Check credentials!")
        return False

    print("Connected to MT5!")
    return True

# === PLACE ORDER IN MT5 ===
def place_order(order_type, volume,symbol):
    """Places a BUY/SELL order in MT5"""

    # Ensure MT5 is connected
    if not connect_mt5():
        return {"error": "Failed to connect to MT5"}    
    
    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found!")
        return {"error": "Invalid symbol"}

    # Get the latest price
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if order_type == "buy" else tick.bid
   
    # Close any existing opposite trades before opening a new one
    close_opposite_trade(order_type,symbol)

    # Prepare the order request
    order_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,    
        "deviation": DEVIATION,
        "magic": MAGIC_NUMBER,
        "comment": "TradingView Signal",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print(order_request)
    # Send order
    order_result = mt5.order_send(order_request)
    print("Order Request:", order_result)    

    if order_result is None or order_result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed: {order_result}")
        return {"error": "Trade execution failed", "details": str(order_result)}

    print(f"Trade executed: {order_type.upper()} at {price} with volume {volume}")
    TRADE_LOG.append({"type": order_type, "price": price, "volume": volume})
    
    return {"message": f"Trade executed: {order_type.upper()} at {price} with volume {volume}"}

# === CLOSE EXISTING TRADE IF OPPOSITE SIGNAL COMES ===
def close_opposite_trade(new_order_type,symbol):
    """Closes previous trades if the opposite signal is received"""
    
    open_positions = mt5.positions_get(symbol=symbol)
    if open_positions is None or len(open_positions) == 0:
        return  

    for position in open_positions:
        if (position.type == mt5.ORDER_TYPE_BUY and new_order_type == "sell") or \
           (position.type == mt5.ORDER_TYPE_SELL and new_order_type == "buy"):
            
            print(f"Open Order Found: Ticket {position.ticket}, Volume {position.volume}, Type {position.type}")

            bid_price = mt5.symbol_info_tick(position.symbol).bid  # Price for closing BUY
            ask_price = mt5.symbol_info_tick(position.symbol).ask  # Price for closing SELL
            price = bid_price if position.type == mt5.ORDER_TYPE_BUY else ask_price

            if (position.type == mt5.ORDER_TYPE_BUY):
                print("----Closing existing Buy order----")
                close_trade(position)
            else:
                print("----Closing existing Sell order----")
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,  # Correct action for closing trades
                    "position": position.ticket,
                    "symbol": position.symbol,
                    "volume": position.volume,
                    "price": price,  # Correct price for closing the trade
                    "deviation": 10,
                    "magic": 123456,
                    "comment": "Closing opposite trade",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,  # Use RETURN if IOC fails
                }    

                print("🔍 Close Request:", close_request)            
                close_result = mt5.order_send(close_request)
                print("🔍 Close Request:", close_request) 
                print(close_result.retcode)

                if close_result is None or close_result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f"Failed to close trade: {close_result}")
                else:
                    print(f"Closed previous trade before opening new {new_order_type} trade.")

# === CLOSE EXISTING TRADE DIRECTLY ===
def close_signal_order(symbol):
    """Closes previous trades if the opposite signal is received"""

    # Ensure MT5 is connected
    if not connect_mt5():
        return {"error": "Failed to connect to MT5"}        
    
    open_positions = mt5.positions_get(symbol=symbol)
    if open_positions is None or len(open_positions) == 0:
        return  

    for position in open_positions:
        print(f"Open Order Found: Ticket {position.ticket}, Volume {position.volume}, Type {position.type}")

        bid_price = mt5.symbol_info_tick(position.symbol).bid  # Price for closing BUY
        ask_price = mt5.symbol_info_tick(position.symbol).ask  # Price for closing SELL
        price = bid_price if position.type == mt5.ORDER_TYPE_BUY else ask_price

        if (position.type == mt5.ORDER_TYPE_BUY):
            print("----Closing existing Buy order----")
            close_trade(position)
        else:
            print("----Closing existing Sell order----")
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,  # Correct action for closing trades
                "position": position.ticket,
                "symbol": position.symbol,
                "volume": position.volume,
                "price": price,  # Correct price for closing the trade
                "deviation": 10,
                "magic": 123456,
                "comment": "Closing opposite trade",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,  # Use RETURN if IOC fails
            }    

            print("Close Request:", close_request)            

            close_result = mt5.order_send(close_request)

            print("Close Request:", close_request) 
            print(close_result.retcode)

            if close_result is None or close_result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Failed to close trade: {close_result}")
            else:
                print(f"Closed existing order {close_result}.")


# === BUY ORDER ===
def close_trade(position):
    symbol_info = mt5.symbol_info_tick(position.symbol)
    if not symbol_info:
        print(f"Failed to get symbol info for {position.symbol}")
        return
    
    bid_price = symbol_info.bid  
    ask_price = symbol_info.ask  
    if bid_price == 0 or ask_price == 0:
        print(f"Invalid bid/ask prices: Bid={bid_price}, Ask={ask_price}")
        return

    print(f"Open Order Found: Ticket {position.ticket}, Volume {position.volume}, Type {position.type}")

    if position.type != mt5.ORDER_TYPE_BUY:
        print(f"Expected a BUY order but found Type {position.type}")
        return

    # Correct price and type for closing
    price = bid_price if position.type == mt5.ORDER_TYPE_BUY else ask_price
    order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY

    print(f"Using price {price} to close {position.symbol}")

    positions = mt5.positions_get(symbol=position.symbol)
    if not positions:
        print(f"No open positions found for {position.symbol}")
        return

    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,  
        "position": position.ticket,
        "symbol": position.symbol,
        "volume": position.volume,
        "price": price,  
        "deviation": 10,
        "magic": 123456,
        "comment": "Closing opposite trade",
        "type": order_type,  # Correct order type
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,  # Broker may not support FOK
    }

    close_result = mt5.order_send(close_request)

    if close_result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to close trade: {close_result}")
        print("Retcode:", close_result.retcode)
        print("Last MT5 Error:", mt5.last_error())  
    else:
        print(f"Trade Closed Successfully: {close_result}")

# === FLASK WEBHOOK HANDLER ===
@app.route('/webhook', methods=['POST'])
def webhook():
    """Receives webhook signals from TradingView and places trades"""

    global btc_cnter,xau_cnter

    # Ensure MT5 is connected
    if not connect_mt5():
        return {"error": "Failed to connect to MT5"}       

    # webhook processing
    data = request.json
    print("-------------------------------------")
    print(f"Webhook Received: {data}")
    if "action" in data and "symbol" in data:
        symbol = data["symbol"]
        close_signal_order(symbol)
        return jsonify({"message": f"All positions closed for {symbol}"}), 200
    elif "signal" not in data or "volume" not in data or "symbol" not in data:
        return jsonify({"error": "Invalid payload"}), 400
    signal = data["signal"].lower()
    volume = data["volume"]
    symbol = data["symbol"]
    symbol = str(symbol)

    ###################################################################
    if symbol in "XAUUSD":
        #-- This is for handling for impulsive buy and sell ---#
        if signal == "ibuy" or signal == "isell":
            open_positions = mt5.positions_get(symbol=symbol)
            if open_positions is not None and len(open_positions) > 0:
                open_positions = open_positions[0]
                print(xau_cnter)
                if open_positions.type == mt5.ORDER_TYPE_BUY and signal == "ibuy" and (xau_cnter < 10) :
                    xau_cnter = xau_cnter + 1
                    return jsonify(place_order("buy", volume, symbol))
                elif open_positions.type == mt5.ORDER_TYPE_SELL and signal == "isell" and (xau_cnter < 10) :
                    xau_cnter = xau_cnter + 1
                    return jsonify(place_order("sell", volume, symbol))
                else:
                    return jsonify({"Info ": "skipping the trade"}), 400
        xau_cnter = 0
        #-- This is for normal buy and sell
        if signal == "buy":
            return jsonify(place_order("buy", volume, symbol))
        elif signal == "sell":
            return jsonify(place_order("sell", volume, symbol))
        else:
            return jsonify({"error": "Unknown signal"}), 400
    ######################################################################
    elif symbol in "BTCUSD":
        #-- This is for handling for impulsive buy and sell ---#
        if signal == "ibuy" or signal == "isell":
            open_positions = mt5.positions_get(symbol=symbol)
            if open_positions is not None and len(open_positions) > 0:
                open_positions = open_positions[0]
                print(btc_cnter)
                if open_positions.type == mt5.ORDER_TYPE_BUY and signal == "ibuy" and (btc_cnter < 10) :
                    btc_cnter = btc_cnter + 1
                    return jsonify(place_order("buy", volume, symbol))
                elif open_positions.type == mt5.ORDER_TYPE_SELL and signal == "isell" and (btc_cnter < 10) :
                    btc_cnter = btc_cnter + 1
                    return jsonify(place_order("sell", volume, symbol))
                else:
                    return jsonify({"Info ": "skipping the trade"}), 400
        btc_cnter = 0
        #-- This is for normal buy and sell
        if signal == "buy":
            return jsonify(place_order("buy", volume, symbol))
        elif signal == "sell":
            return jsonify(place_order("sell", volume, symbol))
        else:
            return jsonify({"error": "Unknown signal"}), 400
    ####################################################################################        

# === START FLASK SERVER ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)